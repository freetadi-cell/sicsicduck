#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本
從銀行官網直接獲取定期存款利率，MoneyHero 作為後備數據來源

每日 11:00 由 cron 執行

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
import random

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
# 銀行官網 URL 映射
# ============================================================
BANK_URLS = {
    # 傳統銀行
    '滙豐銀行': {
        'hkd': 'https://www.hsbc.com.hk/zh-hk/accounts/products/time-deposits/',
        'usd': 'https://www.hsbc.com.hk/zh-hk/accounts/products/time-deposits/',
    },
    '中銀香港': {
        'hkd': 'https://www.bochk.com/tc/deposits/promotion/timedeposits.html',
        'usd': 'https://www.bochk.com/tc/deposits/promotion/timedeposits.html',
    },
    '恒生銀行': {
        'hkd': 'https://www.hangseng.com/cms/tc/rates/td-rates',
        'usd': 'https://www.hangseng.com/cms/tc/rates/td-rates',
    },
    '渣打銀行': {
        'hkd': 'https://www.sc.com/hk/deposit/rates/',
        'usd': 'https://www.sc.com/hk/deposit/rates/',
    },
    '富邦銀行': {
        'hkd': 'https://www.fubonbank.com.hk/tc/rate/time-deposit',
        'usd': 'https://www.fubonbank.com.hk/tc/rate/time-deposit',
    },
    '工銀亞洲': {
        'hkd': 'https://www.icbcasia.com/ICBC/%E9%87%91%E8%9E%8D%E4%BF%A1%E6%81%AF/%E5%AD%98%E6%AC%BE%E5%88%A9%E7%8E%87/',
        'usd': 'https://www.icbcasia.com/ICBC/%E9%87%91%E8%9E%8D%E4%BF%A1%E6%81%AF/%E5%AD%98%E6%AC%BE%E5%88%A9%E7%8E%87/',
    },
    '東亞銀行': {
        'hkd': 'https://www.hkbea.com/html/tc/rate_dps.php',
        'usd': 'https://www.hkbea.com/html/tc/rate_dps.php',
    },
    '中信銀行（國際）': {
        'hkd': 'https://www.cncbi.com.hk/tc/rates/deposit-rates',
        'usd': 'https://www.cncbi.com.hk/tc/rates/deposit-rates',
    },
    '星展銀行': {
        'hkd': 'https://www.dbs.com.hk/personal-zh/deposits/rates',
        'usd': 'https://www.dbs.com.hk/personal-zh/deposits/rates',
    },
    '南洋商業銀行': {
        'hkd': 'https://www.nanyangbank.com.hk/tc/deposit-rates',
        'usd': 'https://www.nanyangbank.com.hk/tc/deposit-rates',
    },
    '交通銀行': {
        'hkd': 'https://www.bankcomm.com.hk/HK/PersonalBanking/Deposit/TimeDeposit/TimeDepositRates',
        'usd': 'https://www.bankcomm.com.hk/HK/PersonalBanking/Deposit/TimeDeposit/TimeDepositRates',
    },
    '上海商業銀行': {
        'hkd': 'https://www.shacombank.com.hk/tc/rates/deposits.html',
        'usd': 'https://www.shacombank.com.hk/tc/rates/deposits.html',
    },
    '大眾銀行': {
        'hkd': 'https://www.publicbank.com.hk/en/personal-banking/deposits/time-deposit',
        'usd': 'https://www.publicbank.com.hk/en/personal-banking/deposits/time-deposit',
    },
    '招商永隆': {
        'hkd': 'https://www.winglungbank.com/en/personal/deposit/time-deposit',
        'usd': 'https://www.winglungbank.com/en/personal/deposit/time-deposit',
    },
    '創興銀行': {
        'hkd': 'https://www.chbank.com/tc/personal/deposit/time-deposit',
        'usd': 'https://www.chbank.com/tc/personal/deposit/time-deposit',
    },
    # 虛擬銀行
    '富融銀行': {
        'hkd': 'https://www.fusionbank.com/deposit.html?lang=en',
        'usd': 'https://www.fusionbank.com/deposit.html?lang=en',
    },
    '天星銀行': {
        'hkd': 'https://mox.com/promotions/time-deposit/',
        'usd': 'https://mox.com/promotions/time-deposit/',
    },
    '眾安銀行': {
        'hkd': 'https://bank.za.group/en/deposit',
        'usd': 'https://bank.za.group/en/deposit',
    },
    'PAO Bank': {
        'hkd': 'https://www.paobank.com/en/deposit.html',
        'usd': 'https://www.paobank.com/en/deposit.html',
    },
}

# MoneyHero 後備數據源
MONEYHERO_URLS = {
    'hkd': 'https://www.moneyhero.com.hk/zh/banking/blog/time-deposit/hkd',
    'usd': 'https://www.moneyhero.com.hk/zh/banking/blog/time-deposit/usd',
}

# ============================================================
# HTTP fetch utility
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None

# ============================================================
# Agent-browser utility
# ============================================================

def agent_browser_cmd(cmd: str, timeout_ms: int = 30000) -> Optional[str]:
    """Run an agent-browser command and return output."""
    try:
        full_cmd = f'agent-browser {cmd}'
        logger.debug(f"Running: {full_cmd}")
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=(timeout_ms // 1000) + 10
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.warning(f"agent-browser {cmd}: stderr={result.stderr[:200]}")
            return result.stdout.strip() if result.stdout else None
    except subprocess.TimeoutExpired:
        logger.warning(f"agent-browser {cmd}: timeout")
        return None
    except FileNotFoundError:
        logger.warning("agent-browser not found, skipping browser automation")
        return None
    except Exception as e:
        logger.warning(f"agent-browser {cmd}: {e}")
        return None

def scrape_bank_with_agent_browser(bank_name: str, url: str, currency: str) -> Optional[Dict[str, Dict]]:
    """Use agent-browser to scrape a bank's deposit page for rates."""
    logger.info(f"Scraping {bank_name} ({currency}) with agent-browser: {url}")
    
    # 打開頁面
    output = agent_browser_cmd(f'open "{url}" --timeout 30000')
    if output is None:
        logger.warning(f"Failed to open page for {bank_name}")
        return None
    
    # 等待頁面加載
    time.sleep(2)
    agent_browser_cmd('wait 3000', timeout_ms=10000)
    
    # 獲取頁面快照
    snapshot = agent_browser_cmd('snapshot -i -c', timeout_ms=15000)
    if not snapshot:
        logger.warning(f"No snapshot for {bank_name}")
        agent_browser_cmd('close')
        return None
    
    # 嘗試獲取頁面文本
    page_text = agent_browser_cmd('eval "document.body.innerText"', timeout_ms=10000)
    if not page_text:
        page_text = snapshot
    
    # 關閉瀏覽器
    agent_browser_cmd('close')
    
    # 解析利率數據
    rates = parse_rates_from_text(bank_name, currency, page_text)
    
    if rates:
        logger.info(f"Found rates for {bank_name} ({currency}): {rates}")
        return rates
    else:
        logger.warning(f"No rates found for {bank_name} ({currency})")
        return None

def parse_rates_from_text(bank_name: str, currency: str, text: str) -> Optional[Dict[str, Dict]]:
    """Parse rates from page text."""
    rates = {}
    
    # 定義常見的存款期限關鍵詞
    period_patterns = {
        '1m': [r'1\s*個月', r'1\s*月', r'1\s*month', r'1m', r'30\s*天', r'30\s*days'],
        '3m': [r'3\s*個月', r'3\s*月', r'3\s*month', r'3m', r'90\s*天', r'90\s*days'],
        '6m': [r'6\s*個月', r'6\s*月', r'6\s*month', r'6m', r'180\s*天', r'180\s*days'],
        '12m': [r'12\s*個月', r'12\s*月', r'12\s*month', r'12m', r'1\s*年', r'1\s*year', r'365\s*天', r'365\s*days'],
    }
    
    # 利率模式
    rate_pattern = r'(\d+\.\d+)\s*%'
    
    # 按行處理文本
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # 檢查是否包含利率相關關鍵詞
        if any(keyword in line_lower for keyword in ['利率', '息率', 'rate', 'interest', '%', 'p.a.', '年利率']):
            # 檢查每個存款期限
            for period, patterns in period_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, line_lower, re.IGNORECASE):
                        # 在當前行和後續幾行中尋找利率
                        search_lines = lines[i:i+5]
                        for search_line in search_lines:
                            rate_matches = re.findall(rate_pattern, search_line)
                            if rate_matches:
                                try:
                                    rate_val = float(rate_matches[0])
                                    # 只取最高利率
                                    if period not in rates or rate_val > rates[period]['rate']:
                                        # 嘗試提取最低存款額
                                        min_deposit = extract_min_deposit(search_line)
                                        note = extract_note(search_line, bank_name, currency, period)
                                        
                                        rates[period] = {
                                            'rate': rate_val,
                                            'min_deposit': min_deposit,
                                            'note': note,
                                            'source': 'bank'
                                        }
                                    break
                                except ValueError:
                                    continue
    
    return rates if rates else None

def extract_min_deposit(text: str) -> Optional[int]:
    """Extract minimum deposit amount from text."""
    # 尋找金額模式
    patterns = [
        r'最低\s*存款\s*(\d+[\d,]*)\s*(港元|港幣|HKD|USD|美元)',
        r'起存\s*金額\s*(\d+[\d,]*)\s*(港元|港幣|HKD|USD|美元)',
        r'(\d+[\d,]*)\s*(港元|港幣|HKD|USD|美元)\s*或以上',
        r'(\d+[\d,]*)\s*(港元|港幣|HKD|USD|美元)\s*起',
        r'min\.?\s*(\d+[\d,]*)\s*(hkd|usd)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                amount_str = match.group(1).replace(',', '')
                return int(amount_str)
            except (ValueError, IndexError):
                continue
    
    return None

def extract_note(text: str, bank_name: str, currency: str, period: str) -> str:
    """Extract note from text."""
    # 簡單的筆記提取
    notes = []
    
    # 檢查是否新資金
    if any(keyword in text.lower() for keyword in ['新資金', 'new fund', 'new money']):
        notes.append('新資金')
    
    # 檢查是否網上辦理
    if any(keyword in text.lower() for keyword in ['網上', '手機', 'online', 'mobile', 'app']):
        notes.append('網上/手機辦理')
    
    # 檢查是否有特別優惠
    if any(keyword in text.lower() for keyword in ['優惠', 'promotion', '特優']):
        notes.append('優惠利率')
    
    if notes:
        return '，'.join(notes)
    else:
        return f'{bank_name} {currency.upper()} {period} 定期存款'

# ============================================================
# MoneyHero 後備數據源
# ============================================================

def scrape_moneyhero(currency: str) -> Dict[str, Dict]:
    """Scrape rates from MoneyHero as fallback."""
    logger.info(f"Scraping MoneyHero for {currency.upper()} rates...")
    
    url = MONEYHERO_URLS.get(currency)
    if not url:
        return {}
    
    html = fetch_url(url)
    if not html:
        logger.warning(f"Failed to fetch MoneyHero {currency} page")
        return {}
    
    # MoneyHero 頁面結構較複雜，這裡使用簡單的文本匹配
    rates = {}
    
    # 尋找表格或列表中的利率數據
    lines = html.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # 檢查是否包含銀行名稱和利率
        for bank_name in BANK_URLS.keys():
            if bank_name in line or any(keyword in line_lower for keyword in bank_name.lower().split()):
                # 在附近行中尋找利率
                for j in range(max(0, i-3), min(len(lines), i+4)):
                    rate_match = re.search(r'(\d+\.\d+)\s*%', lines[j])
                    if rate_match:
                        try:
                            rate_val = float(rate_match.group(1))
                            # 簡單的存款期限判斷
                            period = '3m'  # 默認3個月
                            if any(term in lines[j].lower() for term in ['1個月', '1月', '1 month']):
                                period = '1m'
                            elif any(term in lines[j].lower() for term in ['6個月', '6月', '6 month']):
                                period = '6m'
                            elif any(term in lines[j].lower() for term in ['12個月', '12月', '12 month', '1年']):
                                period = '12m'
                            
                            if bank_name not in rates:
                                rates[bank_name] = {}
                            
                            rates[bank_name][period] = {
                                'rate': rate_val,
                                'min_deposit': None,
                                'note': 'MoneyHero 數據*',
                                'source': 'moneyhero'
                            }
                        except ValueError:
                            continue
    
    logger.info(f"Found {len(rates)} banks from MoneyHero {currency}")
    return rates

# ============================================================
# 主更新邏輯
# ============================================================

def update_bank_rates(bank_name: str, currency: str) -> Optional[Dict[str, Dict]]:
    """Update rates for a specific bank and currency."""
    # 檢查是否有官網 URL
    if bank_name in BANK_URLS and currency in BANK_URLS[bank_name]:
        url = BANK_URLS[bank_name][currency]
        
        # 使用 agent-browser 嘗試獲取數據
        rates = scrape_bank_with_agent_browser(bank_name, url, currency)
        if rates:
            return rates
    
    # 如果官網失敗，返回 None（將在後續使用 MoneyHero 數據）
    return None

def update_rates():
    """Main function to update rates.json."""
    logger.info("=" * 50)
    logger.info("HK Deposit Rates Update - Direct from Bank Websites")
    logger.info(f"Time: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    # 加載現有數據
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(RATES_FILE):
        logger.error("rates.json not found!")
        return False
    
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 獲取 MoneyHero 後備數據
    moneyhero_hkd_rates = scrape_moneyhero('hkd')
    moneyhero_usd_rates = scrape_moneyhero('usd')
    
    # 更新每家銀行
    banks_updated = 0
    banks_failed = 0
    
    for bank in data.get('banks', []):
        bank_name = bank['name']
        logger.info(f"Processing {bank_name}...")
        
        bank_updated = False
        
        # 處理每種貨幣
        for currency in ['hkd', 'usd']:
            # 嘗試從官網獲取數據
            rates = update_bank_rates(bank_name, currency)
            
            if rates:
                # 成功從官網獲取數據
                for period, rate_info in rates.items():
                    if period in bank[currency]:
                        bank[currency][period] = rate_info
                        bank_updated = True
                logger.info(f"  {currency.upper()}: Updated from bank website")
            else:
                # 使用 MoneyHero 後備數據
                moneyhero_rates = moneyhero_hkd_rates if currency == 'hkd' else moneyhero_usd_rates
                
                if bank_name in moneyhero_rates:
                    for period, rate_info in moneyhero_rates[bank_name].items():
                        if period in bank[currency]:
                            # 只更新如果當前沒有數據或 MoneyHero 數據較新
                            current_rate = bank[currency][period].get('rate')
                            new_rate = rate_info.get('rate')
                            
                            if current_rate is None or (new_rate is not None and new_rate > current_rate):
                                bank[currency][period] = rate_info
                                bank_updated = True
                    
                    if bank_updated:
                        logger.info(f"  {currency.upper()}: Updated from MoneyHero")
                else:
                    logger.warning(f"  {currency.upper()}: No data available")
        
        if bank_updated:
            banks_updated += 1
        else:
            banks_failed += 1
        
        # 隨機延遲以避免被屏蔽
        time.sleep(random.uniform(1, 3))
    
    # 更新時間戳和數據源
    data['last_updated'] = datetime.now(HKT).strftime('%Y-%m-%dT%H:%M:%S+08:00')
    data['source'] = '各銀行官網 / MoneyHero (後備)'
    
    # 保存數據
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("=" * 50)
    logger.info(f"Update completed: {banks_updated} banks updated, {banks_failed} banks failed")
    logger.info(f"Timestamp: {data['last_updated']}")
    logger.info("=" * 50)
    
    return banks_updated > 0

def main():
    success = update_rates()
    if success:
        logger.info("✅ Update completed successfully")
        return 0
    else:
        logger.error("❌ Update failed or no banks updated")
        return 1

if __name__ == '__main__':
    sys.exit(main())