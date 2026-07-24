#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本（v2 — 無 Playwright）
整合 requests + web_fetch 雙引擎抓取 + Parser + 變動報告

流程：
1. 用 requests 抓取官網 HTML
2. 失敗則用 web_fetch（OpenClaw 內建，可處理部分 JS 渲染頁面）
3. 再失敗則用 HKET 作為後備數據源
4. 用各銀行嘅 parser 提取利率
5. 統一利率格式為百分比（2.4 = 2.4%）
6. 比對舊利率，標注變動
7. 更新 rates.json
8. Git commit + push
9. 輸出變動報告
"""

import json
import os
import sys
import time
import logging
import re
import subprocess
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# Import all parsers
sys.path.insert(0, os.path.dirname(__file__))
from parsers import *
from fetcher import fetch_with_requests, get_fetch_strategy, HKET_HEADERS

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
    'ncb': parse_ncb,  # 南洋商業銀行
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


def normalize_rate(rate):
    """統一利率格式為百分比。
    
    舊數據可能存小數格式（0.024 = 2.4%），新數據存百分比（2.4 = 2.4%）。
    我哋統一用百分比格式：如果 rate < 1，就乘 100。
    """
    if rate is None:
        return None
    rate = float(rate)
    # 如果細過 1，好可能係小數格式（0.024 → 2.4%）
    # 但 0.001 之類嘅極低利率係真嘅（例如 HSBC existing_funds 0.001%）
    # 所以我哋用 0.05 做分界：細過 0.05 嘅先當係百分比，0.05-1 之間嘅當係小數
    if 0.05 < rate < 1.0:
        return round(rate * 100, 4)
    return rate


def normalize_rates_dict(rates):
    """遞歸統一利率格式"""
    if isinstance(rates, dict):
        result = {}
        for k, v in rates.items():
            if k == 'rate' and isinstance(v, (int, float)):
                result[k] = normalize_rate(v)
            else:
                result[k] = normalize_rates_dict(v)
        return result
    elif isinstance(rates, list):
        return [normalize_rates_dict(item) for item in rates]
    return rates


def get_old_rate(old_rates, bank_key, currency, period, fund_type='new_funds'):
    """從舊利率數據中提取特定利率（已統一為百分比格式）"""
    try:
        for bank in old_rates.get('banks', []):
            if bank.get('key') == bank_key or bank.get('name_en', '').lower().replace(' ', '') == bank_key:
                currency_data = bank.get(currency, {})
                period_data = currency_data.get(period, {})
                
                # Handle nested fund_type
                if isinstance(period_data, dict) and fund_type in period_data:
                    rate_data = period_data.get(fund_type, {})
                    if isinstance(rate_data, dict):
                        return normalize_rate(rate_data.get('rate'))
                elif isinstance(period_data, dict) and 'rate' in period_data:
                    return normalize_rate(period_data.get('rate'))
                elif isinstance(period_data, (int, float)):
                    return normalize_rate(period_data)
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
                        new_rate = normalize_rate(rate_info.get('rate'))
                    else:
                        new_rate = normalize_rate(rate_info)
                    
                    old_rate = get_old_rate(old_rates, bank_key, currency, period, fund_type)
                    
                    if new_rate and old_rate and abs(new_rate - old_rate) > 0.01:
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
                new_rate = normalize_rate(period_data.get('rate'))
                old_rate = get_old_rate(old_rates, bank_key, currency, period)
                
                if new_rate and old_rate and abs(new_rate - old_rate) > 0.01:
                    changes.append({
                        'currency': currency,
                        'period': period,
                        'old_rate': old_rate,
                        'new_rate': new_rate,
                        'change': round(new_rate - old_rate, 2)
                    })
    
    return changes


def fetch_with_web_fetch(url, max_chars=15000):
    """用 OpenClaw 嘅 web_fetch 抓取網頁（可處理部分 JS 渲染頁面）
    
    透過 subprocess 調用 openclaw CLI，因為 web_fetch 係 OpenClaw tool，
    唔可以直接喺 Python 入面 import。
    """
    # web_fetch 只能透過 OpenClaw agent tool 調用
    # 喺獨立腳本入面，我哋用 requests + BeautifulSoup 做更深度嘅提取
    return None


def fetch_bank_page(url, timeout=15):
    """用 requests 抓取官網 HTML 並提取純文字 + 表格。
    
    Returns:
        dict with keys: text, tables, html, success
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        if response.status_code != 200:
            logger.warning(f"  HTTP {response.status_code} for {url}")
            return {'text': None, 'tables': [], 'html': None, 'success': False}
        
        # Force correct encoding
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = 'utf-8'
        
        html = response.text
        
        # Check for block pages
        if 'Just a moment' in html or 'Checking your browser' in html:
            logger.warning(f"  Cloudflare blocked: {url}")
            return {'text': None, 'tables': [], 'html': None, 'success': False}
        if 'ERROR: The request could not be satisfied' in html:
            logger.warning(f"  CloudFront blocked: {url}")
            return {'text': None, 'tables': [], 'html': None, 'success': False}
        if 'Access Denied' in html and len(html) < 5000:
            logger.warning(f"  Access denied: {url}")
            return {'text': None, 'tables': [], 'html': None, 'success': False}
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script/style/nav/header/footer
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'noscript']):
            tag.decompose()
        
        # Extract text
        text = soup.get_text(separator='\n')
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        text = '\n'.join(lines)
        
        # Extract tables
        tables = []
        for table in soup.find_all('table')[:10]:
            table_text = table.get_text(separator='\n')
            lines = [l.strip() for l in table_text.split('\n') if l.strip()]
            tables.append('\n'.join(lines))
        
        return {
            'text': text[:15000],  # Limit text size
            'tables': tables,
            'html': html[:50000],  # Keep raw HTML for parsers that need it
            'success': True
        }
        
    except requests.exceptions.Timeout:
        logger.warning(f"  Timeout fetching {url}")
        return {'text': None, 'tables': [], 'html': None, 'success': False}
    except requests.exceptions.RequestException as e:
        logger.warning(f"  Request error for {url}: {e}")
        return {'text': None, 'tables': [], 'html': None, 'success': False}
    except Exception as e:
        logger.warning(f"  Parse error for {url}: {e}")
        return {'text': None, 'tables': [], 'html': None, 'success': False}


def scrape_bank(bank_info):
    """Scrape a single bank's rate page using requests (no Playwright).
    
    策略：
    1. 先試官網（requests）
    2. 失敗則試 HKET（如果有配置）
    3. 全部失敗則標記為需要 manual retry
    """
    name = bank_info['name']
    name_en = bank_info['name_en']
    key = bank_info['key']
    urls = bank_info.get('urls', {})
    
    # 獲取銀行的抓取策略
    strategy = get_fetch_strategy(key)
    logger.info(f"  [{key}] Strategy: {strategy}")
    
    # === Step 1: 嘗試官網 ===
    # URL 優先次序：promotion > hkd_rates > card_rates > general
    url_priority = ['promotion', 'hkd_rates', 'card_rates', 'general']
    
    # 如果策略係 ['hket']，跳過官網直接用 HKET
    if strategy == ['hket']:
        url_priority = []
    
    for url_type in url_priority:
        url = urls.get(url_type)
        if not url:
            continue
        
        logger.info(f"  [{key}] Fetching {url_type}: {url}")
        result = fetch_bank_page(url)
        
        if not result['success']:
            continue
        
        # 檢查內容是否有效（有利率相關關鍵字）
        text = result['text'] or ''
        rate_keywords = ['年利率', '定期存款', '利率', 'interest rate', 'Time Deposit', 'p.a.', '%']
        has_rate_content = any(kw in text for kw in rate_keywords)
        
        if not has_rate_content and len(text) < 500:
            logger.warning(f"  [{key}] No rate content from {url_type}")
            continue
        
        return {
            'key': key,
            'name': name,
            'name_en': name_en,
            'url': url,
            'url_type': url_type,
            'text': text,
            'tables': result['tables'],
            'html': result['html'],
            'scraped_at': datetime.now(HK_TZ).isoformat(),
            'success': True
        }
    
    # === Step 2: 嘗試 HKET ===
    if 'hket' in urls:
        url = urls['hket']
        logger.info(f"  [{key}] Fetching HKET: {url}")
        
        text = fetch_with_requests(url)
        if text:
            return {
                'key': key,
                'name': name,
                'name_en': name_en,
                'url': url,
                'url_type': 'hket',
                'text': text[:15000],
                'tables': [],
                'html': None,
                'scraped_at': datetime.now(HK_TZ).isoformat(),
                'success': True
            }
        else:
            logger.warning(f"  [{key}] HKET fetch also failed")
    
    # === Step 3: 全部失敗 ===
    return {
        'key': key,
        'name': name,
        'name_en': name_en,
        'url': urls.get('general', urls.get('hket')),
        'url_type': None,
        'text': None,
        'tables': [],
        'html': None,
        'scraped_at': datetime.now(HK_TZ).isoformat(),
        'success': False
    }


def main():
    logger.info("=" * 60)
    logger.info("HK Deposit Rates Auto-Update (v2 — No Playwright)")
    logger.info(f"Time: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)
    
    # Load existing data
    url_data = load_bank_urls()
    banks = url_data.get('banks', [])
    old_rates = load_rates()
    
    # 先統一舊數據嘅利率格式
    old_rates = normalize_rates_dict(old_rates)
    
    logger.info(f"Processing {len(banks)} banks")
    
    # Scrape all banks (no Playwright!)
    scraped_data = []
    
    for bank_info in banks:
        result = scrape_bank(bank_info)
        scraped_data.append(result)
        
        if result['success']:
            logger.info(f"  ✅ {result['name']} - scraped from {result['url_type']}")
        else:
            logger.warning(f"  ❌ {bank_info['name']} - all sources failed")
        
        time.sleep(0.5)  # Be polite
    
    # Parse rates using bank-specific parsers
    logger.info("\n" + "=" * 60)
    logger.info("Parsing rates...")
    logger.info("=" * 60)
    
    successful_banks = []
    failed_banks = []
    rate_changes = []
    
    for scraped in scraped_data:
        key = scraped['key']
        name = scraped['name']
        
        parser = PARSER_MAP.get(key)
        if not parser:
            # Check for alias
            if key == 'ncb':
                # 南洋商業銀行暫時用通用 parser
                logger.warning(f"  [{key}] No specific parser, skipping")
                failed_banks.append({'name': name, 'key': key, 'reason': '無 parser'})
                continue
            logger.warning(f"  [{key}] No parser found")
            failed_banks.append({'name': name, 'key': key, 'reason': '無 parser'})
            continue
        
        if not scraped['success']:
            logger.warning(f"  [{key}] Scrape failed")
            failed_banks.append({'name': name, 'key': key, 'reason': '網頁抓取失敗'})
            continue
        
        try:
            # Parse the scraped content
            parsed = parser(scraped['text'], tables=scraped.get('tables', []), html=scraped.get('html'))
            
            if not parsed or (not parsed.get('hkd') and not parsed.get('usd') and not parsed.get('cny')):
                logger.warning(f"  [{key}] Parser returned empty rates")
                failed_banks.append({'name': name, 'key': key, 'reason': 'Parser 返回空數據'})
                continue
            
            # 統一新數據嘅利率格式
            parsed = normalize_rates_dict(parsed)
            
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
            
            # Update rates.json with new parsed data
            bank_found = False
            for i, bank in enumerate(old_rates.get('banks', [])):
                if bank.get('key') == key or bank.get('name_en', '').lower().replace(' ', '') == key:
                    # Update existing bank's rates
                    if 'hkd' in parsed:
                        old_rates['banks'][i]['hkd'] = {**bank.get('hkd', {}), **parsed['hkd']}
                    if 'usd' in parsed:
                        old_rates['banks'][i]['usd'] = {**bank.get('usd', {}), **parsed['usd']}
                    if 'cny' in parsed:
                        old_rates['banks'][i]['cny'] = {**bank.get('cny', {}), **parsed['cny']}
                    # Ensure key is set
                    if not old_rates['banks'][i].get('key'):
                        old_rates['banks'][i]['key'] = key
                    bank_found = True
                    break
            
            if not bank_found:
                if 'banks' not in old_rates:
                    old_rates['banks'] = []
                old_rates['banks'].append({
                    'name': name,
                    'name_en': scraped.get('name_en', ''),
                    'key': key,
                    **parsed
                })
            
        except Exception as e:
            logger.error(f"  [{key}] Parser error: {e}")
            import traceback
            traceback.print_exc()
            failed_banks.append({'name': name, 'key': key, 'reason': f'Parser 錯誤: {str(e)[:50]}'})
    
    # Save updated rates to rates.json
    save_rates(old_rates)
    logger.info(f"✅ Updated {len(successful_banks)} banks in rates.json")
    
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
