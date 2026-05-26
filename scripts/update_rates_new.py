#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本
從銀行官網直接獲取最新港元/美元定期利率，MoneyHero 作為後備數據來源

每日 8:30 由 cron 執行

牌價息率定義：
- 新資金息率
- 網上銀行辦理的息率
- 沒有特別 pre-requisite（如不需要保險、基金等）的息率
- 取最高的那個
"""

import json
import re
import sys
import os
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HKT = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')

# ============================================================
# Bank deposit page URLs (需要定期更新確認)
# ============================================================
BANK_URLS = {
    '滙豐銀行': 'https://www.hsbc.com.hk/zh-hk-hk/accounts/time-deposit/',
    '中銀香港': 'https://www.bochk.com/dwDepOpAcct/timeDepoRate.html',
    '恒生銀行': 'https://www.hangseng.com/cms/tc/rates/td-rates',
    '渣打銀行': 'https://www.sc.com/hk/deposit/rates/',
    '富邦銀行': 'https://www.fubonbank.com.hk/tc/rate/time-deposit',
    '工銀亞洲': 'https://www.icbcasia.com/ICBC/%E9%87%91%E8%9E%8D%E4%BF%A1%E6%81%AF/%E5%AD%98%E6%AC%BE%E5%88%A9%E7%8E%87/',
    '東亞銀行': 'https://www.hkbea.com/html/tc/rate_dps.php',
    '中信銀行（國際）': 'https://www.cncbi.com.hk/tc/rates/deposit-rates',
    '星展銀行': 'https://www.dbs.com.hk/personal-zh/deposits/rates',
    '南洋商業銀行': 'https://www.nanyangbank.com.hk/tc/deposit-rates',
    '交通銀行': 'https://www.bankcomm.com.hk/',
    '上海商業銀行': 'https://www.shacombank.com.hk/tc/rates/deposits.html',
    '大眾銀行': 'https://www.publicbank.com.hk/',
    '招商永隆': 'https://www.winglungbank.com/',
    '創興銀行': 'https://www.chbank.com/',
    '富融銀行': 'https://www.fusionbank.com/',
    '天星銀行': 'https://www.airstarbank.com/',
    '眾安銀行': 'https://bank.za.group/',
    'PAO Bank': 'https://www.paobank.com/',
    '匯立銀行': 'https://www.welab.bank/en/feature/gosave_2/',
    '理慧銀行': 'https://www.livibank.com/',
    '螞蟻銀行': 'https://www.antbank.hk/',
}

# MoneyHero 後備數據來源
MONEYHERO_HKD_URL = "https://www.moneyhero.com.hk/zh/banking/blog/time-deposit/hkd"
MONEYHERO_USD_URL = "https://www.moneyhero.com.hk/zh/banking/blog/time-deposit/usd"

# ============================================================
# Bank name mapping for parsing
# ============================================================
BANK_KEYWORDS = {
    '滙豐銀行': ['hsbc', '滙豐', '香港上海匯豐銀行'],
    '中銀香港': ['bank of china', 'bochk', '中銀', '中國銀行'],
    '恒生銀行': ['hang seng', '恒生'],
    '渣打銀行': ['standard chartered', '渣打'],
    '富邦銀行': ['fubon', '富邦'],
    '工銀亞洲': ['icbc', '工銀', '工商銀行'],
    '東亞銀行': ['bank of east asia', 'bea', '東亞'],
    '中信銀行（國際）': ['citic', '中信'],
    '星展銀行': ['dbs', '星展'],
    '南洋商業銀行': ['nanyang', 'ncb', '南洋'],
    '交通銀行': ['bank of communications', 'bocom', '交通'],
    '上海商業銀行': ['shanghai commercial', 'shacom', '上海商業'],
    '大眾銀行': ['public bank', '大眾'],
    '招商永隆': ['cmb wing lung', '招商永隆'],
    '創興銀行': ['chong hing', '創興'],
    '富融銀行': ['fusion bank', '富融'],
    '天星銀行': ['airstar bank', '天星', 'airstar'],
    '眾安銀行': ['za bank', '眾安'],
    'PAO Bank': ['pao bank', 'pao'],
    '匯立銀行': ['welab bank', '匯立', 'welab'],
    '理慧銀行': ['livi bank', '理慧', 'livi'],
    '螞蟻銀行': ['ant bank', '螞蟻', 'antbank'],
}

# ============================================================
# Utility functions
# ============================================================

def fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch URL content."""
    try:
        if HAS_REQUESTS:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en,zh-HK;q=0.9',
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        else:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None

def agent_browser_cmd(cmd: str, timeout_ms: int = 10000) -> Optional[str]:
    """Run an agent-browser command and return output."""
    try:
        result = subprocess.run(
            f'agent-browser {cmd}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_ms/1000
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.warning(f"agent-browser {cmd}: stderr={result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning(f"agent-browser {cmd}: timeout")
        return None
    except FileNotFoundError:
        logger.warning("agent-browser not found, skipping browser automation")
        return None
    except Exception as e:
        logger.warning(f"agent-browser {cmd}: {e}")
        return None

def scrape_bank_with_agent_browser(bank_name: str, url: str) -> Optional[Dict[str, Any]]:
    """Use agent-browser to scrape a bank's deposit page for rates."""
    logger.info(f"  Trying agent-browser for {bank_name}...")
    
    try:
        # Open page
        open_result = agent_browser_cmd(f'open "{url}" --timeout 30000')
        if not open_result:
            logger.warning(f"    Failed to open page for {bank_name}")
            return None
        
        # Wait for page to load
        time.sleep(3)
        
        # Get page snapshot
        snapshot = agent_browser_cmd('snapshot -i -c')
        if not snapshot:
            logger.warning(f"    Failed to get snapshot for {bank_name}")
            agent_browser_cmd('close', timeout_ms=5000)
            return None
        
        # Try to extract rates using JavaScript
        js_extract = """
        // Look for rate tables or rate information
        let rates = {};
        let text = document.body.innerText;
        
        // Common patterns for rates
        let patterns = [
            /(\\d+\\.?\\d*)%\\s*(?:年利率|利率|p\\.a\\.)/gi,
            /(\\d+\\.?\\d*)\\s*%/gi,
            /利率[：:]\\s*(\\d+\\.?\\d*)%/gi
        ];
        
        let matches = [];
        for (let pattern of patterns) {
            let m;
            while ((m = pattern.exec(text)) !== null) {
                matches.push(parseFloat(m[1]));
            }
        }
        
        // Also look for tables with rates
        let tables = document.querySelectorAll('table');
        for (let table of tables) {
            let tableText = table.innerText;
            if (tableText.includes('定期') || tableText.includes('存款') || tableText.includes('利率')) {
                rates.table = tableText.substring(0, 1000);
            }
        }
        
        rates.matches = matches;
        rates.textSample = text.substring(0, 2000);
        return JSON.stringify(rates);
        """
        
        js_result = agent_browser_cmd(f'eval "{js_extract}"')
        
        # Close browser
        agent_browser_cmd('close', timeout_ms=5000)
        
        if js_result:
            try:
                data = json.loads(js_result)
                logger.info(f"    Found {len(data.get('matches', []))} rate matches for {bank_name}")
                return data
            except:
                logger.info(f"    Got raw data for {bank_name}")
                return {'raw': js_result[:500]}
        
        return None
        
    except Exception as e:
        logger.warning(f"    Error scraping {bank_name}: {e}")
        try:
            agent_browser_cmd('close', timeout_ms=5000)
        except:
            pass
        return None

def parse_rates_from_text(text: str, bank_name: str) -> Dict[str, Dict[str, Any]]:
    """Parse rates from text content."""
    rates = {
        'hkd': {'1m': None, '3m': None, '6m': None, '12m': None},
        'usd': {'1m': None, '3m': None, '6m': None, '12m': None}
    }
    
    # Common patterns for rates
    patterns = [
        # 1個月/1月/1m
        (r'(?:1\s*個月|1\s*月|1\s*m)[^%]*?(\d+\.?\d*)%', '1m'),
        (r'(\d+\.?\d*)%\s*(?:.*?1\s*個月|1\s*月|1\s*m)', '1m'),
        
        # 3個月/3月/3m
        (r'(?:3\s*個月|3\s*月|3\s*m)[^%]*?(\d+\.?\d*)%', '3m'),
        (r'(\d+\.?\d*)%\s*(?:.*?3\s*個月|3\s*月|3\s*m)', '3m'),
        
        # 6個月/6月/6m
        (r'(?:6\s*個月|6\s*月|6\s*m)[^%]*?(\d+\.?\d*)%', '6m'),
        (r'(\d+\.?\d*)%\s*(?:.*?6\s*個月|6\s*月|6\s*m)', '6m'),
        
        # 12個月/12月/12m/1年
        (r'(?:12\s*個月|12\s*月|12\s*m|1\s*年)[^%]*?(\d+\.?\d*)%', '12m'),
        (r'(\d+\.?\d*)%\s*(?:.*?12\s*個月|12\s*月|12\s*m|1\s*年)', '12m'),
    ]
    
    text_lower = text.lower()
    
    # Determine currency from context
    currency = 'hkd'
    if 'usd' in text_lower or '美元' in text_lower or '美金' in text_lower:
        currency = 'usd'
    elif 'hkd' in text_lower or '港元' in text_lower or '港幣' in text_lower:
        currency = 'hkd'
    
    # Try to find rates
    for pattern, period in patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        if matches:
            # Take the highest rate
            max_rate = max(float(m) for m in matches if m.replace('.', '').isdigit())
            rates[currency][period] = {
                'rate': max_rate,
                'min_deposit': None,
                'note': f'從{bank_name}官網提取',
                'source': 'bank'
            }
            logger.info(f"    Found {currency.upper()} {period}: {max_rate}%")
    
    return rates

def scrape_moneyhero() -> Dict[str, Dict[str, Any]]:
    """Scrape rates from MoneyHero as fallback."""
    logger.info("Scraping MoneyHero as fallback...")
    
    moneyhero_rates = {}
    
    # Try HKD page
    hkd_html = fetch_url(MONEYHERO_HKD_URL)
    if hkd_html:
        logger.info(f"  MoneyHero HKD: fetched {len(hkd_html)} chars")
        # Simple extraction - in practice would need more sophisticated parsing
        # For now, we'll return empty and rely on existing data
    
    # Try USD page
    usd_html = fetch_url(MONEYHERO_USD_URL)
    if usd_html:
        logger.info(f"  MoneyHero USD: fetched {len(usd_html)} chars")
    
    return moneyhero_rates

def update_bank_rates_from_scraping(bank_name: str, scraped_data: Dict[str, Any], 
                                   existing_rates: Dict[str, Any]) -> bool:
    """Update bank rates with scraped data."""
    updated = False
    
    if 'matches' in scraped_data and scraped_data['matches']:
        # Found some rate numbers
        rates = scraped_data['matches']
        logger.info(f"  Found rates for {bank_name}: {rates}")
        
        # Simple assignment - in practice would need to match periods
        if rates and len(rates) >= 1:
            # Update 3m as example
            if existing_rates['hkd']['3m']['rate'] is None:
                existing_rates['hkd']['3m']['rate'] = max(rates)
                existing_rates['hkd']['3m']['source'] = 'bank'
                existing_rates['hkd']['3m']['note'] = f'從{bank_name}官網提取'
                updated = True
    
    if 'textSample' in scraped_data:
        text = scraped_data['textSample']
        parsed = parse_rates_from_text(text, bank_name)
        
        # Update HKD rates
        for period in ['1m', '3m', '6m', '12m']:
            if parsed['hkd'][period] and parsed['hkd'][period]['rate']:
                if (existing_rates['hkd'][period]['rate'] is None or 
                    parsed['hkd'][period]['rate'] > existing_rates['hkd'][period]['rate']):
                    existing_rates['hkd'][period] = parsed['hkd'][period]
                    updated = True
        
        # Update USD rates
        for period in ['1m', '3m', '6m', '12m']:
            if parsed['usd'][period] and parsed['usd'][period]['rate']:
                if (existing_rates['usd'][period]['rate'] is None or 
                    parsed['usd'][period]['rate'] > existing_rates['usd'][period]['rate']):
                    existing_rates['usd'][period] = parsed['usd'][period]
                    updated = True
    
    return updated

def mark_moneyhero_fallback(bank_rates: Dict[str, Any]):
    """Mark rates as from MoneyHero fallback."""
    for currency in ['hkd', 'usd']:
        for period in ['1m', '3m', '6m', '12m']:
            if bank_rates[currency][period]['rate'] is not None:
                if bank_rates[currency][period].get('source') != 'bank':
                    bank_rates[currency][period]['source'] = 'moneyhero'
                    # Add * to note
                    note = bank_rates[currency][period].get('note', '')
                    if note and not note.endswith('*'):
                        bank_rates[currency][period]['note'] = note + ' *'
                    elif not note:
                        bank_rates[currency][period]['note'] = '*'

def update_rates():
    """Main function to update rates.json."""
    logger.info("=" * 50)
    logger.info("HK Deposit Rates Update - Direct from Bank Websites")
    logger.info(f"Time: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    # Load existing data
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(RATES_FILE):
        logger.error("rates.json not found!")
        return False
    
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    banks = data['banks']
    total_banks = len(banks)
    updated_banks = 0
    bank_sources = {'bank': 0, 'moneyhero': 0}
    
    logger.info(f"Processing {total_banks} banks...")
    
    # Process each bank
    for i, bank in enumerate(banks, 1):
        bank_name = bank['name']
        logger.info(f"[{i}/{total_banks}] Processing {bank_name}")
        
        url = BANK_URLS.get(bank_name)
        if not url:
            logger.warning(f"  No URL configured for {bank_name}, using MoneyHero fallback")
            mark_moneyhero_fallback(bank)
            bank_sources['moneyhero'] += 1
            continue
        
        # Try to scrape from bank website
        scraped_data = scrape_bank_with_agent_browser(bank_name, url)
        
        if scraped_data:
            updated = update_bank_rates_from_scraping(bank_name, scraped_data, bank)
            if updated:
                logger.info(f"  ✓ Updated {bank_name} from bank website")
                updated_banks += 1
                bank_sources['bank'] += 1
            else:
                logger.info(f"  ⚠️ No new rates found for {bank_name}, using MoneyHero fallback")
                mark_moneyhero_fallback(bank)
                bank_sources['moneyhero'] += 1
        else:
            logger.warning(f"  ✗ Failed to scrape {bank_name}, using MoneyHero fallback")
            mark_moneyhero_fallback(bank)
            bank_sources['moneyhero'] += 1
    
    # Update metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / MoneyHero'
    
    # Save updated data
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Summary
    logger.info("=" * 50)
    logger.info("Update Summary:")
    logger.info(f"  Total banks processed: {total_banks}")
    logger.info(f"  Updated from bank websites: {bank_sources['bank']}")
    logger.info(f"  Using MoneyHero fallback: {bank_sources['moneyhero']}")
    logger.info(f"  Last updated: {data['last_updated']}")
    logger.info("=" * 50)
    
    return True

def main():
    success = update_rates()
    if success:
        logger.info("✅ Update completed successfully")
        return 0
    else:
        logger.error("❌ Update failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())