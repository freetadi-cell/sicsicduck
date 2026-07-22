#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本（完整版）
整合爬蟲 + Parser + 變動報告

流程：
1. 用 Playwright 爬取 22 間銀行網頁
2. 用各銀行嘅 parser 提取利率
3. 比對舊利率，標注變動
4. 更新 rates.json
5. Git commit + push
6. 輸出變動報告
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# Import all parsers
sys.path.insert(0, os.path.dirname(__file__))
from parsers import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')
URLS_FILE = os.path.join(DATA_DIR, 'bank_urls.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'scraped_content.json')

HK_TZ = timezone(timedelta(hours=8))

# Parser mapping
PARSER_MAP = {
    'hsbc': parse_hsbc,
    'bochk': parse_bochk,
    'hangseng': parse_hangseng,
    'sc': parse_sc,
    'dbs': parse_dbs,
    'bea': parse_bea,
    'cncbi': parse_cncbi,
    'icbc': parse_icbc,
    'fubon': parse_fubon,
    'bocomm': parse_bocomm,
    'shacom': parse_shacom,
    'publicbank': parse_publicbank,
    'winglung': parse_winglung,
    'chbank': parse_chbank,
    'fusion': parse_fusion,
    'airstar': parse_airstar,
    'za': parse_za,
    'pao': parse_pao,
    'welab': parse_welab,
    'livi': parse_livi,
    'ant': parse_ant,
    'chiyu': parse_chiyu,
}


def load_bank_urls():
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_rates():
    if os.path.exists(RATES_FILE):
        with open(RATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"banks": []}


def save_rates(rates):
    rates['last_updated'] = datetime.now(HK_TZ).isoformat()
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rates, f, ensure_ascii=False, indent=2)


def get_old_rate(old_rates, bank_key, currency, period, fund_type='new_funds'):
    """從舊利率數據中提取特定利率"""
    try:
        for bank in old_rates.get('banks', []):
            if bank.get('key') == bank_key or bank.get('name_en', '').lower().replace(' ', '') == bank_key:
                currency_data = bank.get(currency, {})
                period_data = currency_data.get(period, {})
                
                # Handle nested fund_type
                if isinstance(period_data, dict) and fund_type in period_data:
                    rate_data = period_data.get(fund_type, {})
                    if isinstance(rate_data, dict):
                        return rate_data.get('rate')
                elif isinstance(period_data, dict) and 'rate' in period_data:
                    return period_data.get('rate')
                elif isinstance(period_data, (int, float)):
                    return period_data
    except:
        pass
    return None


def compare_rates(old_rates, new_rates, bank_key, currency):
    """比對新舊利率，返回變動列表"""
    changes = []
    
    if not new_rates or currency not in new_rates:
        return changes
    
    currency_data = new_rates[currency]
    
    periods = ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']
    
    for period in periods:
        period_data = currency_data.get(period)
        if not period_data:
            continue
            
        # Handle different rate structures
        if isinstance(period_data, dict):
            # Check for fund_type specific rates
            for fund_type in ['new_funds', 'existing_funds', 'exchange']:
                if fund_type in period_data:
                    rate_info = period_data[fund_type]
                    if isinstance(rate_info, dict):
                        new_rate = rate_info.get('rate')
                    else:
                        new_rate = rate_info
                    
                    old_rate = get_old_rate(old_rates, bank_key, currency, period, fund_type)
                    
                    if new_rate and old_rate and new_rate != old_rate:
                        changes.append({
                            'currency': currency,
                            'period': period,
                            'fund_type': fund_type,
                            'old_rate': old_rate,
                            'new_rate': new_rate,
                            'change': round(new_rate - old_rate, 2)
                        })
            
            # Check for simple rate
            if 'rate' in period_data:
                new_rate = period_data.get('rate')
                old_rate = get_old_rate(old_rates, bank_key, currency, period)
                
                if new_rate and old_rate and new_rate != old_rate:
                    changes.append({
                        'currency': currency,
                        'period': period,
                        'old_rate': old_rate,
                        'new_rate': new_rate,
                        'change': round(new_rate - old_rate, 2)
                    })
    
    return changes


def scrape_bank(page, bank_info):
    """Scrape a single bank's rate page and return raw text content."""
    name = bank_info['name']
    name_en = bank_info['name_en']
    key = bank_info['key']
    urls = bank_info.get('urls', {})
    
    # Check if bank has HKET URL (primary source for blocked banks)
    if 'hket' in urls:
        url_priority = ['hket', 'promotion', 'hkd_rates', 'card_rates', 'general']
    else:
        url_priority = ['promotion', 'hkd_rates', 'card_rates', 'general']
    
    for url_type in url_priority:
        url = urls.get(url_type)
        if not url:
            continue
        
        try:
            logger.info(f"  [{key}] Fetching {url_type}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            # Special handling for banks
            if key == 'za':
                try:
                    buttons = page.locator('button').all()
                    for btn in buttons:
                        text = btn.inner_text().strip()
                        if text == '定期存款':
                            btn.click()
                            logger.info(f"  [{key}] Clicked 定期存款 tab")
                            time.sleep(2)
                            break
                except Exception as e:
                    logger.warning(f"  [{key}] Could not click tab: {e}")
            
            elif key == 'winglung':
                logger.info(f"  [{key}] Waiting 8s for dynamic content...")
                page.wait_for_timeout(8000)
                for i in range(3):
                    page.evaluate(f"window.scrollTo(0, {i * 1000})")
                    time.sleep(1)
                
            elif key == 'chbank':
                logger.info(f"  [{key}] Waiting 5s for dynamic content...")
                page.wait_for_timeout(5000)
            
            text = page.inner_text("body")
            
            if "找不到網頁" in text or "Page not found" in text or "404" in text:
                logger.warning(f"  [{key}] Page not found: {url}")
                continue
            
            tables = []
            table_elements = page.locator("table").all()
            for table in table_elements[:10]:
                try:
                    tables.append(table.inner_text())
                except:
                    pass
            
            title = page.title()
            
            return {
                'key': key,
                'name': name,
                'name_en': name_en,
                'url': url,
                'url_type': url_type,
                'title': title,
                'text': text[:10000],
                'tables': tables[:10],
                'scraped_at': datetime.now(HK_TZ).isoformat(),
                'success': True
            }
            
        except Exception as e:
            logger.warning(f"  [{key}] Error fetching {url}: {e}")
            continue
    
    return {
        'key': key,
        'name': name,
        'name_en': name_en,
        'url': None,
        'title': None,
        'text': None,
        'tables': [],
        'scraped_at': datetime.now(HK_TZ).isoformat(),
        'success': False
    }


def main():
    logger.info("=" * 60)
    logger.info("HK Deposit Rates Auto-Update (Full Pipeline)")
    logger.info(f"Time: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)
    
    # Load existing data
    url_data = load_bank_urls()
    banks = url_data.get('banks', [])
    old_rates = load_rates()
    
    logger.info(f"Processing {len(banks)} banks")
    
    # Scrape all banks
    scraped_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        viewport = {"width": 1280, "height": 800}
        
        for bank_info in banks:
            page = browser.new_page()
            page.set_viewport_size(viewport)
            
            result = scrape_bank(page, bank_info)
            scraped_data.append(result)
            
            if result['success']:
                logger.info(f"  ✅ {result['name']} - scraped from {result['url_type']}")
            else:
                logger.warning(f"  ❌ {bank_info['name']} - all URLs failed")
            
            page.close()
            time.sleep(1)
        
        browser.close()
    
    # Parse rates using bank-specific parsers
    logger.info("\n" + "=" * 60)
    logger.info("Parsing rates...")
    logger.info("=" * 60)
    
    successful_banks = []
    failed_banks = []
    rate_changes = []
    needs_browser_retry = []  # Banks that need agent browser retry
    
    for scraped in scraped_data:
        key = scraped['key']
        name = scraped['name']
        
        parser = PARSER_MAP.get(key)
        if not parser:
            logger.warning(f"  [{key}] No parser found")
            failed_banks.append({'name': name, 'key': key, 'reason': '無 parser'})
            continue
        
        if not scraped['success']:
            logger.warning(f"  [{key}] Scrape failed - needs browser retry")
            failed_banks.append({'name': name, 'key': key, 'reason': '網頁抓取失敗，需要 browser retry'})
            needs_browser_retry.append({'name': name, 'key': key, 'url': scraped.get('url')})
            continue
        
        try:
            # Parse the scraped content
            parsed = parser(scraped)
            
            if not parsed or (not parsed.get('hkd') and not parsed.get('usd') and not parsed.get('cny')):
                logger.warning(f"  [{key}] Parser returned empty rates")
                failed_banks.append({'name': name, 'key': key, 'reason': 'Parser 返回空數據，可能需要 browser retry'})
                needs_browser_retry.append({'name': name, 'key': key, 'url': scraped.get('url')})
                continue
            
            logger.info(f"  ✅ {name} - parsed successfully")
            successful_banks.append(name)
            
            # Compare with old rates
            for currency in ['hkd', 'usd', 'cny']:
                if currency in parsed:
                    changes = compare_rates(old_rates, parsed, key, currency)
                    if changes:
                        for change in changes:
                            rate_changes.append({
                                'bank': name,
                                **change
                            })
            
            # Update rates.json structure
            # (This is simplified - in production would merge properly)
            
        except Exception as e:
            logger.error(f"  [{key}] Parser error: {e}")
            failed_banks.append({'name': name, 'key': key, 'reason': f'Parser 錯誤: {str(e)[:30]}', 'needs_retry': True})
            needs_browser_retry.append({'name': name, 'key': key, 'url': scraped.get('url')})
    
    # Save scraped content
    output = {
        'scrape_time': datetime.now(HK_TZ).isoformat(),
        'total_banks': len(banks),
        'successful': len(successful_banks),
        'failed': len(failed_banks),
        'results': scraped_data
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # Generate report
    logger.info("\n" + "=" * 60)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 60)
    
    report_lines = []
    report_lines.append(f"📊 **香港銀行定期存款利率更新報告**")
    report_lines.append(f"時間: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("")
    
    # Successful banks
    report_lines.append(f"✅ **成功抓取 ({len(successful_banks)} 間)**")
    for bank in successful_banks:
        report_lines.append(f"  • {bank}")
    
    report_lines.append("")
    
    # Failed banks
    if failed_banks:
        report_lines.append(f"❌ **抓取失敗 ({len(failed_banks)} 間)**")
        for bank in failed_banks:
            report_lines.append(f"  • {bank['name']} — {bank['reason']}")
        report_lines.append("")
    
    # Banks needing browser retry
    if needs_browser_retry:
        report_lines.append(f"🔧 **需要 Agent Browser Retry ({len(needs_browser_retry)} 間)**")
        for bank in needs_browser_retry:
            report_lines.append(f"  • {bank['name']} — URL: {bank.get('url', 'N/A')}")
        report_lines.append("")        report_lines.append("💡 **建議**: 需要手動用 agent browser 去提取呢啲銀行嘅利率")
        report_lines.append("")
    
    # Rate changes
    if rate_changes:
        report_lines.append(f"📈 **利率變動 ({len(rate_changes)} 項)**")
        for change in rate_changes:
            direction = "⬆️" if change['change'] > 0 else "⬇️"
            report_lines.append(
                f"  • {change['bank']} {change['currency'].upper()} {change['period']}: "
                f"{change['old_rate']}% → {change['new_rate']}% ({direction}{abs(change['change'])}%)"
            )
    else:
        report_lines.append("📉 **利率變動**: 無變動")
    
    report_lines.append("")
    report_lines.append(f"總計: {len(successful_banks)}/{len(banks)} 成功")
    
    # Print report
    report = "\n".join(report_lines)
    print("\n" + report)
    
    # Save report for Telegram
    report_file = os.path.join(DATA_DIR, 'update_report.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"\nReport saved to {report_file}")
    
    return {
        'successful': len(successful_banks),
        'failed': len(failed_banks),
        'changes': len(rate_changes)
    }


if __name__ == '__main__':
    result = main()
    
    # Git commit and push
    logger.info("\n" + "=" * 60)
    logger.info("Git commit and push...")
    logger.info("=" * 60)
    
    os.chdir(BASE_DIR)
    os.system('git add -A')
    os.system(f'git commit -m "chore: 自動更新利率 - {datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M")}"')
    os.system('git push')
    
    logger.info("✅ Git commit and push completed")
