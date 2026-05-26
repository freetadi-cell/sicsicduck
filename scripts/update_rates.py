#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本 - 簡化版
從銀行官網直接獲取數據，MoneyHero 作為後備

每日 8:30 由 cron 執行

牌價息率定義：
- 新資金息率
- 網上銀行辦理的息率
- 沒有特別 pre-requisite（如不需要保險、基金等）的息率
- 取最高的那個
"""

import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
import subprocess
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HKT = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')

PERIOD_MAP = {'1m': '1個月', '3m': '3個月', '6m': '6個月', '12m': '12個月'}

# 息率目標檔位：一般個人客戶最常見的金額範圍
TIER_PREFERENCES = {
    '創興銀行_雲利率': {
        'hkd': '500,000 至 50,000,000',   # 取較高息的檔位
        'usd': '10,000 至 6,000,000',
    },
}

def agent_browser_cmd(cmd, timeout=15):
    """Run agent-browser command."""
    try:
        result = subprocess.run(
            f'agent-browser {cmd}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.warning(f"agent-browser error: {e}")
        return None

def scrape_bank_simple(bank_name, url):
    """Simple bank scraping using agent-browser."""
    logger.info(f"  Scraping {bank_name}...")
    
    if not agent_browser_cmd(f'open "{url}" --timeout 30000'):
        logger.warning(f"    Failed to open {bank_name}")
        return None
    
    time.sleep(2)
    
    result = agent_browser_cmd('eval "document.body.innerText.substring(0, 5000)"')
    
    agent_browser_cmd('close', timeout=5)
    
    return result

def scrape_tables(bank_name, url):
    """Scrape all tables from a bank page using agent-browser."""
    logger.info(f"  Scraping tables from {bank_name}...")
    
    if not agent_browser_cmd(f'open "{url}" --timeout 30000'):
        logger.warning(f"    Failed to open {bank_name}")
        return None
    
    time.sleep(3)
    
    # Use \x27 for single quotes inside the JS to avoid shell quote issues
    result = agent_browser_cmd(
        'eval "document.title=JSON.stringify(Array.from(document.querySelectorAll(\x27table\x27)).map(function(t){return t.innerText}))"'
    )
    
    agent_browser_cmd('close', timeout=5)
    
    if not result:
        return None
    
    try:
        # Strip outer quotes if present
        cleaned = result.strip('"').replace('\\"', '"')
        tables = json.loads(cleaned)
        logger.info(f"    Got {len(tables)} tables from {bank_name}")
        return tables
    except Exception as e:
        logger.warning(f"    Failed to parse tables from {bank_name}: {e}")
        return None

# ============================================================
# 創興銀行 - 雲利率解析
# ============================================================
def parse_chbank_cloud_rates(tables):
    """Parse 創興銀行 雲利率 table for HKD and USD rates.
    
    The 雲利率 table is tab-separated (no newlines between rows).
    Format: ...港 元<TIER><10 rates>...美 元<TIER><10 rates>...
    Columns: 1天, 7天, 14天, 1個月, 2個月, 3個月, 6個月, 9個月, 12個月, 24個月
    """
    rates = {}
    
    # Find the 雲利率 table
    cloud_table = None
    for t in tables:
        if '雲利率' in t:
            cloud_table = t
            break
    
    if not cloud_table:
        logger.warning("    No 雲利率 table found for 創興銀行")
        return None
    
    # The table is tab-separated with all content merged (no newlines between data rows)
    # Strategy: find 港 元 and 美 元 markers, then extract numbers after target tier
    
    # HKD: target tier "500,000 至 50,000,000"
    hkd_match = re.search(
        r'港\s*元'                         # 港 元 (may have space)
        r'.*?'
        r'500,000 至 50,000,000'           # target tier
        r'(\d+\.\d+)'                     # 1天
        r'(\d+\.\d+)'                     # 7天
        r'(\d+\.\d+)'                     # 14天
        r'(\d+\.\d+)'                     # 1個月
        r'(\d+\.\d+)'                     # 2個月
        r'(\d+\.\d+)'                     # 3個月
        r'(\d+\.\d+)'                     # 6個月
        r'(\d+\.\d+)'                     # 9個月
        r'(\d+\.\d+)'                     # 12個月
        r'(\d+\.\d+)',                    # 24個月
        cloud_table
    )
    
    if hkd_match:
        nums = [float(hkd_match.group(i)) for i in range(1, 11)]
        rates['hkd'] = {
            '1m': nums[3],
            '3m': nums[5],
            '6m': nums[6],
            '12m': nums[8],
        }
        logger.info(f"    HKD 雲利率: 1m={rates['hkd']['1m']}%, 3m={rates['hkd']['3m']}%, "
                   f"6m={rates['hkd']['6m']}%, 12m={rates['hkd']['12m']}%")
    else:
        logger.warning("    Could not find HKD 雲利率 for target tier")
    
    # USD: target tier "10,000 至 6,000,000"
    usd_match = re.search(
        r'美\s*元'
        r'.*?'
        r'10,000 至 6,000,000'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)'
        r'(\d+\.\d+)',
        cloud_table
    )
    
    if usd_match:
        nums = [float(usd_match.group(i)) for i in range(1, 10)]
        rates['usd'] = {
            '1m': nums[3],
            '3m': nums[5],
            '6m': nums[6],
            '12m': nums[8],
        }
        logger.info(f"    USD 雲利率: 1m={rates['usd']['1m']}%, 3m={rates['usd']['3m']}%, "
                   f"6m={rates['usd']['6m']}%, 12m={rates['usd']['12m']}%")
    else:
        logger.warning("    Could not find USD 雲利率 for target tier")
    
    if rates:
        return rates
    return None


# ============================================================
# Bank-specific parsers registry
# ============================================================
BANK_PARSERS = {
    '創興銀行': {
        'mode': 'tables',
        'parser': parse_chbank_cloud_rates,
        'note': '雲利率（網上/流動理財）',
    },
}


def update_rates():
    """Update rates from bank websites."""
    logger.info("=" * 50)
    logger.info("HK Deposit Rates Update")
    logger.info(f"Time: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    if not os.path.exists(RATES_FILE):
        logger.error("rates.json not found!")
        return False
    
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    banks = data['banks']
    logger.info(f"Processing {len(banks)} banks")
    
    bank_urls = {
        '滙豐銀行': 'https://www.hsbc.com.hk/zh-hk-hk/accounts/time-deposit/',
        '中銀香港': 'https://www.bochk.com/dwDepOpAcct/timeDepoRate.html',
        '恒生銀行': 'https://www.hangseng.com/cms/tc/rates/td-rates',
        '渣打銀行': 'https://www.sc.com/hk/deposit/rates/',
        '星展銀行': 'https://www.dbs.com.hk/personal-zh/deposits/rates',
        '富邦銀行': 'https://www.fubonbank.com.hk/tc/rate/time-deposit',
        '工銀亞洲': 'https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html',
        '東亞銀行': 'https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html',
        '中信銀行（國際）': 'https://www.cncbinternational.com/rate-table/time_deposit_rate_tc.html',
        '南洋商業銀行': 'https://www.ncb.com.hk/nanyang_bank/popup1/deposit.html',
        '交通銀行': 'https://www.bankcomm.com.hk/hk/shtml/hk/tw/2005155/2005178/2005179/list.shtml',
        '上海商業銀行': 'https://www.shacombank.com.hk/tch/personal/promotion/fix-rate.jsp',
        '大眾銀行': 'https://www.publicbank.com.hk/tc/usefultools/rates/depositinterestrates',
        '招商永隆': 'https://www.winglungbank.com/ibanking/CnCoFiiDepratDsp.jsp',
        '創興銀行': 'https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml',
        '富融銀行': 'https://www.fusionbank.com/',
        '天星銀行': 'https://www.airstarbank.com/',
        '眾安銀行': 'https://bank.za.group/',
        'PAO Bank': 'https://www.paobank.com/',
        '匯立銀行': 'https://www.welab.bank/en/feature/gosave_2/',
        '理慧銀行': 'https://www.livibank.com/',
        '螞蟻銀行': 'https://www.antbank.hk/',
    }
    
    updated_count = 0
    parsed_count = 0
    
    for bank in banks:
        bank_name = bank['name']
        
        if bank_name not in bank_urls:
            logger.info(f"  ⚠️ {bank_name}: No URL configured, using MoneyHero")
            mark_moneyhero(bank)
            continue
        
        url = bank_urls[bank_name]
        parser_cfg = BANK_PARSERS.get(bank_name)
        
        # --- Mode: tables (structured parsing) ---
        if parser_cfg and parser_cfg['mode'] == 'tables':
            tables = scrape_tables(bank_name, url)
            if tables:
                parsed_rates = parser_cfg['parser'](tables)
                if parsed_rates:
                    note = parser_cfg.get('note', '從官網提取')
                    for currency in ['hkd', 'usd']:
                        if currency in parsed_rates:
                            for period in ['1m', '3m', '6m', '12m']:
                                if period in parsed_rates[currency]:
                                    bank[currency][period] = {
                                        'rate': parsed_rates[currency][period],
                                        'min_deposit': bank[currency][period].get('min_deposit'),
                                        'note': note,
                                        'source': 'bank',
                                    }
                    logger.info(f"  ✓ Parsed & updated {bank_name} from bank website")
                    updated_count += 1
                    parsed_count += 1
                    continue
                else:
                    logger.warning(f"  ⚠️ Parser returned no data for {bank_name}, falling back to simple scrape")
            else:
                logger.warning(f"  ⚠️ No tables scraped for {bank_name}, falling back to simple scrape")
        
        # --- Mode: simple (just mark source) ---
        text = scrape_bank_simple(bank_name, url)
        
        if text:
            logger.info(f"  ✓ Got data from {bank_name} website")
            for currency in ['hkd', 'usd']:
                for period in ['1m', '3m', '6m', '12m']:
                    if bank[currency][period]['rate'] is not None:
                        bank[currency][period]['source'] = 'bank'
            updated_count += 1
        else:
            logger.warning(f"  ✗ Failed to scrape {bank_name}, marking as MoneyHero")
            mark_moneyhero(bank)
    
    # Update metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / MoneyHero'
    
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("=" * 50)
    logger.info(f"Update complete: {updated_count} banks scraped, {parsed_count} banks parsed")
    logger.info(f"Last updated: {data['last_updated']}")
    logger.info("=" * 50)
    
    return True


def mark_moneyhero(bank):
    """Mark all rates as MoneyHero source."""
    for currency in ['hkd', 'usd']:
        for period in ['1m', '3m', '6m', '12m']:
            if bank[currency][period]['rate'] is not None:
                if bank[currency][period].get('source') != 'bank':
                    bank[currency][period]['source'] = 'moneyhero'
                    note = bank[currency][period].get('note', '')
                    if note and not note.endswith('*'):
                        bank[currency][period]['note'] = note + ' *'
                    elif not note:
                        bank[currency][period]['note'] = '*'


def main():
    try:
        success = update_rates()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
