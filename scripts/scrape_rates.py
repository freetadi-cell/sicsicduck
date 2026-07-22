#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本（Playwright 版本）
由 OpenClaw agent 每朝 8:30 執行

流程：
1. 讀取 bank_urls.json 取得每間銀行嘅利率頁面 URL
2. 用 Playwright 爬每間銀行網頁
3. 輸出原始文字內容，由 OpenClaw agent 理解同提取利率
4. 更新 rates.json
5. Git commit + push
6. 輸出變動總結供 Telegram 通知
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')
URLS_FILE = os.path.join(DATA_DIR, 'bank_urls.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'scraped_content.json')

HK_TZ = timezone(timedelta(hours=8))


def load_bank_urls():
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_rates():
    if os.path.exists(RATES_FILE):
        with open(RATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"banks": []}


def save_rates(rates):
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rates, f, ensure_ascii=False, indent=2)


def scrape_bank(page, bank_info):
    """Scrape a single bank's rate page and return raw text content."""
    name = bank_info['name']
    name_en = bank_info['name_en']
    key = bank_info['key']
    urls = bank_info.get('urls', {})
    
    # Check if bank has HKET URL (primary source for blocked banks)
    # Banks with HKET URL should use it as primary source
    if 'hket' in urls:
        url_priority = ['hket', 'promotion', 'hkd_rates', 'card_rates', 'general']
    else:
        # Try each URL in order: promotion -> hkd_rates -> card_rates -> general
        url_priority = ['promotion', 'hkd_rates', 'card_rates', 'general']
    
    for url_type in url_priority:
        url = urls.get(url_type)
        if not url:
            continue
        
        try:
            logger.info(f"  [{key}] Fetching {url_type}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # Wait for JS to render
            
            # Special handling for banks that need extra wait time or interactions
            
            # ZA Bank - click "定期存款" tab to show rates
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
                    logger.warning(f"  [{key}] Could not click 定期存款 tab: {e}")
            
            # Wing Lung (招商永隆) - needs longer wait for dynamic content
            elif key == 'winglung':
                logger.info(f"  [{key}] Waiting 8s for dynamic content...")
                page.wait_for_timeout(8000)
                # Also try scrolling to trigger lazy-loaded content
                for i in range(3):
                    page.evaluate(f"window.scrollTo(0, {i * 1000})")
                    time.sleep(1)
                
            # Chbank (創興銀行) - needs longer wait for tables
            elif key == 'chbank':
                logger.info(f"  [{key}] Waiting 5s for dynamic content...")
                page.wait_for_timeout(5000)
            
            # Check if page loaded successfully
            text = page.inner_text("body")
            
            if "找不到網頁" in text or "Page not found" in text or "404" in text:
                logger.warning(f"  [{key}] Page not found: {url}")
                continue
            
            # Get tables if any
            tables = []
            table_elements = page.locator("table").all()
            for i, table in enumerate(table_elements[:10]):
                try:
                    tables.append(table.inner_text())
                except:
                    pass
            
            # Get page title
            title = page.title()
            
            return {
                'key': key,
                'name': name,
                'name_en': name_en,
                'url': url,
                'url_type': url_type,
                'title': title,
                'text': text[:8000],  # Limit text size
                'tables': tables[:5],
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
    logger.info("=" * 50)
    logger.info("HK Deposit Rates Scrape (Playwright)")
    logger.info(f"Time: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 50)
    
    # Load bank URLs
    url_data = load_bank_urls()
    banks = url_data.get('banks', [])
    logger.info(f"Processing {len(banks)} banks")
    
    # Scrape all banks
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Set a reasonable viewport
        viewport = {"width": 1280, "height": 800}
        
        for bank_info in banks:
            # Use a fresh page for each bank to avoid redirect conflicts
            page = browser.new_page()
            page.set_viewport_size(viewport)
            
            result = scrape_bank(page, bank_info)
            results.append(result)
            
            if result['success']:
                logger.info(f"  ✅ {result['name']} ({result['name_en']}) - scraped from {result['url_type']}")
            else:
                logger.warning(f"  ❌ {bank_info['name']} ({bank_info['name_en']}) - all URLs failed")
            
            # Close page after each bank to prevent redirect conflicts
            page.close()
            time.sleep(1)  # Small delay between banks
        
        browser.close()
    
    # Save scraped content for agent to process
    output = {
        'scrape_time': datetime.now(HK_TZ).isoformat(),
        'total_banks': len(banks),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\nScrape complete: {output['successful']}/{output['total_banks']} banks scraped")
    logger.info(f"Results saved to {OUTPUT_FILE}")
    
    # Print summary for agent
    print("\n" + "=" * 50)
    print("SCRAPE SUMMARY")
    print("=" * 50)
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"  {status} {r['name']} ({r['name_en']})")
    print(f"\nTotal: {output['successful']}/{output['total_banks']} successful")
    
    return output


if __name__ == '__main__':
    main()
