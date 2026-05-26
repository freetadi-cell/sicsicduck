#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本
從銀行官網直接獲取數據，MoneyHero 作為後備

每日 8:30 由 cron 執行

牌價息率定義：
- 新資金息率
- 網上銀行辦理的息率
- 沒有特別 pre-requisite（如不需要保險、基金等）的息率
- 取最高的那個

Parser 架構：
- scripts/parsers/<bank_key>.py — 每間銀行一個獨立 parser 檔案
- 每個 parser 匯出 parse(text, tables) -> dict or None
- 新增銀行只需加一個 .py 檔案，改 URL 對應即可
"""

import json
import os
import re
import logging
import importlib
from datetime import datetime, timezone, timedelta
import subprocess
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HKT = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')
PARSERS_DIR = os.path.join(SCRIPT_DIR, 'parsers')

# ============================================================
# Bank URL config — parser key → URL
# Parser key must match filename in parsers/<key>.py
# ============================================================
BANK_CONFIG = {
    'hsbc': {
        'name': '滙豐銀行',
        'url': 'https://www.hsbc.com.hk/accounts/offers/deposits/',
    },
    'bochk': {
        'name': '中銀香港',
        'url': 'https://www.bochk.com/dwDepOpAcct/timeDepoRate.html',
    },
    'hangseng': {
        'name': '恒生銀行',
        'url': 'https://www.hangseng.com/cms/tc/rates/td-rates',
    },
    'sc': {
        'name': '渣打銀行',
        'url': 'https://www.sc.com/hk/deposit/rates/',
    },
    'dbs': {
        'name': '星展銀行',
        'url': 'https://www.dbs.com.hk/personal-zh/deposits/rates',
    },
    'fubon': {
        'name': '富邦銀行',
        'url': 'https://www.fubonbank.com.hk/tc/rate/time-deposit',
    },
    'icbc': {
        'name': '工銀亞洲',
        'url': 'https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html',
    },
    'bea': {
        'name': '東亞銀行',
        'url': 'https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html',
    },
    'cncbi': {
        'name': '中信銀行（國際）',
        'url': 'https://www.cncbinternational.com/rate-table/time_deposit_rate_tc.html',
    },
    'ncb': {
        'name': '南洋商業銀行',
        'url': 'https://www.ncb.com.hk/nanyang_bank/popup1/deposit.html',
    },
    'bocomm': {
        'name': '交通銀行',
        'url': 'https://www.bankcomm.com.hk/hk/shtml/hk/tw/2005155/2005178/2005179/list.shtml',
    },
    'shacom': {
        'name': '上海商業銀行',
        'url': 'https://www.shacombank.com.hk/tch/personal/promotion/fix-rate.jsp',
    },
    'publicbank': {
        'name': '大眾銀行',
        'url': 'https://www.publicbank.com.hk/tc/usefultools/rates/depositinterestrates',
    },
    'winglung': {
        'name': '招商永隆',
        'url': 'https://www.winglungbank.com/ibanking/CnCoFiiDepratDsp.jsp',
    },
    'chbank': {
        'name': '創興銀行',
        'url': 'https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml',
        'needs_tables': True,
    },
    'fusion': {
        'name': '富融銀行',
        'url': 'https://www.fusionbank.com/',
    },
    'airstar': {
        'name': '天星銀行',
        'url': 'https://www.airstarbank.com/',
    },
    'za': {
        'name': '眾安銀行',
        'url': 'https://bank.za.group/',
    },
    'pao': {
        'name': 'PAO Bank',
        'url': 'https://www.paobank.com/',
    },
    'welab': {
        'name': '匯立銀行',
        'url': 'https://www.welab.bank/en/feature/gosave_2/',
    },
    'livi': {
        'name': '理慧銀行',
        'url': 'https://www.livibank.com/',
    },
    'ant': {
        'name': '螞蟻銀行',
        'url': 'https://www.antbank.hk/',
    },
}

# ============================================================
# Utility functions
# ============================================================

def run_browser(cmd, timeout=20):
    """Run agent-browser command, return cleaned output or None."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            out = re.sub(r'\x1b\[[0-9;]*m', '', r.stdout).strip()
            return out if out else None
        return None
    except Exception as e:
        logger.warning(f"agent-browser error: {e}")
        return None

def scrape_page(url, wait=5):
    """Open a page and return (text, tables)."""
    run_browser('agent-browser close', timeout=5)
    time.sleep(2)
    
    result = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
    if not result:
        return None, None
    
    time.sleep(wait)
    
    # Get page text
    raw = run_browser('agent-browser eval "document.body.innerText.substring(0, 8000)"', timeout=10)
    text = None
    if raw:
        try:
            text = json.loads(raw)
        except:
            text = raw.strip('"')
    
    # Get tables - use String.fromCharCode to avoid shell quoting issues with 'table'
    tables = []
    js_set = 'document.title=JSON.stringify(Array.from(document.querySelectorAll(String.fromCharCode(116,97,98,108,101))).map(function(t){return t.innerText}))'
    run_browser(f'agent-browser eval "{js_set}"', timeout=10)
    raw_t = run_browser('agent-browser eval "document.title"', timeout=10)
    if raw_t:
        try:
            tables = json.loads(json.loads(raw_t)) if raw_t.startswith('"') else json.loads(raw_t)
        except:
            try:
                tables = json.loads(raw_t)
            except:
                pass
    
    run_browser('agent-browser close', timeout=5)
    time.sleep(1)
    
    return text, tables

def load_parser(parser_key):
    """Dynamically load a parser module. Returns parse function or None."""
    try:
        mod = importlib.import_module(f'parsers.{parser_key}')
        return mod.parse
    except ImportError:
        return None

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

def update_rates():
    """Main function to update rates.json."""
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
    
    # Build name → parser_key lookup
    name_to_key = {}
    for key, cfg in BANK_CONFIG.items():
        name_to_key[cfg['name']] = key
    
    parsed_count = 0
    scraped_count = 0
    failed_banks = []
    
    for bank in banks:
        bank_name = bank['name']
        parser_key = name_to_key.get(bank_name)
        
        if not parser_key:
            logger.info(f"  ⚠️ {bank_name}: No config, using MoneyHero")
            mark_moneyhero(bank)
            continue
        
        cfg = BANK_CONFIG[parser_key]
        url = cfg['url']
        
        # Load parser
        parse_fn = load_parser(parser_key)
        
        if parse_fn:
            # This bank has a dedicated parser
            logger.info(f"  [{parser_key}] Parsing {bank_name}...")
            
            needs_tables = cfg.get('needs_tables', False)
            text, tables = scrape_page(url)
            
            if text is None and tables is None:
                logger.warning(f"  ✗ Failed to scrape {bank_name}")
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
                continue
            
            try:
                result = parse_fn(text, tables)
            except Exception as e:
                logger.warning(f"  ✗ Parser error for {bank_name}: {e}")
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
                continue
            
            if result:
                note = result.get('note', f'從{bank_name}官網提取')
                for currency in ['hkd', 'usd']:
                    if currency in result:
                        for period in ['1m', '3m', '6m', '12m']:
                            if period in result[currency]:
                                bank[currency][period] = {
                                    'rate': result[currency][period],
                                    'min_deposit': bank[currency][period].get('min_deposit'),
                                    'note': note,
                                    'source': 'bank',
                                }
                logger.info(f"  ✓ Parsed {bank_name}: {result}")
                parsed_count += 1
            else:
                logger.warning(f"  ⚠️ Parser returned None for {bank_name}, marking MoneyHero")
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
        else:
            # No parser — just scrape and mark source
            logger.info(f"  [{parser_key}] No parser for {bank_name}, scraping text only...")
            text, _ = scrape_page(url)
            
            if text:
                logger.info(f"  ✓ Got data from {bank_name} (no parser, source marked)")
                for currency in ['hkd', 'usd']:
                    for period in ['1m', '3m', '6m', '12m']:
                        if bank[currency][period]['rate'] is not None:
                            bank[currency][period]['source'] = 'bank'
                scraped_count += 1
            else:
                logger.warning(f"  ✗ Failed to scrape {bank_name}, marking MoneyHero")
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
    
    # Update metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / MoneyHero'
    
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("=" * 50)
    logger.info(f"Update complete:")
    logger.info(f"  Parsed (rates extracted): {parsed_count}")
    logger.info(f"  Scraped (source marked):  {scraped_count}")
    logger.info(f"  Failed/No parser:         {len(failed_banks)}")
    if failed_banks:
        logger.info(f"  Failed banks: {', '.join(failed_banks)}")
    logger.info(f"Last updated: {data['last_updated']}")
    logger.info("=" * 50)
    
    return True


def main():
    try:
        success = update_rates()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
