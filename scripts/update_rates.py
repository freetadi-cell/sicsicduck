#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本 - 簡化版
從銀行官網直接獲取數據，MoneyHero 作為後備

每日 8:30 由 cron 執行
"""

import json
import os
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
    
    # Open page
    if not agent_browser_cmd(f'open "{url}" --timeout 30000'):
        logger.warning(f"    Failed to open {bank_name}")
        return None
    
    time.sleep(2)
    
    # Get page text
    result = agent_browser_cmd('eval "document.body.innerText.substring(0, 5000)"')
    
    # Close browser
    agent_browser_cmd('close', timeout=5)
    
    return result

def update_rates():
    """Update rates from bank websites."""
    logger.info("=" * 50)
    logger.info("HK Deposit Rates Update")
    logger.info(f"Time: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    # Load existing data
    if not os.path.exists(RATES_FILE):
        logger.error("rates.json not found!")
        return False
    
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    banks = data['banks']
    logger.info(f"Processing {len(banks)} banks")
    
    # Bank URLs (主要幾間大銀行)
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
    
    for bank in banks:
        bank_name = bank['name']
        
        if bank_name in bank_urls:
            # Try to scrape from bank website
            text = scrape_bank_simple(bank_name, bank_urls[bank_name])
            
            if text:
                logger.info(f"  ✓ Got data from {bank_name} website")
                # Mark as from bank website
                for currency in ['hkd', 'usd']:
                    for period in ['1m', '3m', '6m', '12m']:
                        if bank[currency][period]['rate'] is not None:
                            bank[currency][period]['source'] = 'bank'
                updated_count += 1
            else:
                logger.warning(f"  ✗ Failed to scrape {bank_name}, marking as MoneyHero")
                # Mark as MoneyHero
                for currency in ['hkd', 'usd']:
                    for period in ['1m', '3m', '6m', '12m']:
                        if bank[currency][period]['rate'] is not None:
                            if bank[currency][period].get('source') != 'bank':
                                bank[currency][period]['source'] = 'moneyhero'
                                # Add * to note
                                note = bank[currency][period].get('note', '')
                                if note and not note.endswith('*'):
                                    bank[currency][period]['note'] = note + ' *'
                                elif not note:
                                    bank[currency][period]['note'] = '*'
        else:
            # Other banks use MoneyHero
            logger.info(f"  ⚠️ {bank_name}: Using MoneyHero data")
            for currency in ['hkd', 'usd']:
                for period in ['1m', '3m', '6m', '12m']:
                    if bank[currency][period]['rate'] is not None:
                        if bank[currency][period].get('source') != 'bank':
                            bank[currency][period]['source'] = 'moneyhero'
                            # Add * to note
                            note = bank[currency][period].get('note', '')
                            if note and not note.endswith('*'):
                                bank[currency][period]['note'] = note + ' *'
                            elif not note:
                                bank[currency][period]['note'] = '*'
    
    # Update metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / MoneyHero'
    
    # Save
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("=" * 50)
    logger.info(f"Update complete: {updated_count} banks from websites")
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
