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
        'url': 'https://www.bochk.com/m/tc/deposits/promotion/timedeposits.html',
    },
    'hangseng': {
        'name': '恒生銀行',
        'url': 'https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html',
    },
    'sc': {
        'name': '渣打銀行',
        'url': 'https://www.sc.com/hk/deposits/online-time-deposit/',
    },
    'dbs': {
        'name': '星展銀行',
        'url': 'https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo',
    },
    'fubon': {
        'name': '富邦銀行',
        'url': 'https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html',
    },
    'icbc': {
        'name': '工銀亞洲',
        'url': 'https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html',
    },
    'bea': {
        'name': '東亞銀行',
        'url': 'https://www.hkbea.com/html/tc/bea-personal-banking-supremeGold-welcome-offer.html',
    },
    'cncbi': {
        'name': '中信銀行（國際）',
        'url': 'https://www.cncbinternational.com/rate-table/time_deposit_rate_tc.html',
    },
    'ncb': {
        'name': '南洋商業銀行',
        'url': 'https://www.ncbinfo.com/tc/content/deposit',
        'skip_scrape': True,  # 利率以圖片形式提供，無法自動抓取
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
        'url': 'https://www.cmbwinglungbank.com/ibanking/CnCoFiiDepratDsp.jsp',
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
        'name': '象象銀行',
        'url': 'https://www.elebank.com/zh-hk/hkprime.html',
        'usd_tab': '美元',  # Need to click USD tab to get USD rates
    },
    'za': {
        'name': '眾安銀行',
        'url': 'https://bank.za.group/',
        'skip_scrape': True,  # 利率只在App內顯示，默認用MoneyHero
    },
    'pao': {
        'name': '平安數字銀行',
        'url': 'https://www.pingandb.com/tc/retail-savings.html',
        'cloudflare_bypass': True,  # 需要自訂 User-Agent 繞過 Cloudflare
    },
    'welab': {
        'name': '匯立銀行',
        'url': 'https://www.welab.bank/en/feature/gosave_2/',
    },
    'livi': {
        'name': '理慧銀行',
        'url': 'https://www.livibank.com/zh_CN/features/livisave.html',
    },
    'ant': {
        'name': '螞蟻銀行',
        'url': 'https://www.antbank.hk/',
    },
    'chiyu': {
        'name': '集友銀行',
        'url': 'https://www.chiyubank.com/cyb/index/zxxx/20230523/index.shtml',
        'pdf_url': 'https://www.chiyubank.com/cyb/attachDir/2026/05/2026052616594318087.pdf',
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

def scrape_page(url, wait=5, cloudflare_bypass=False):
    """Open a page and return (text, tables)."""
    run_browser('agent-browser close', timeout=5)
    time.sleep(2)
    
    if cloudflare_bypass:
        # Set non-headless User-Agent to bypass Cloudflare
        run_browser(
            'agent-browser set headers \'{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}\'',
            timeout=10
        )
    
    result = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
    if not result:
        return None, None
    
    time.sleep(wait)
    
    return _extract_text_tables()

def _extract_text_tables():
    """Extract text and tables from current page (browser must be open)."""
    # Get page text
    raw = run_browser('agent-browser eval "document.body.innerText.substring(0, 8000)"', timeout=10)
    text = None
    if raw:
        try:
            text = json.loads(raw)
        except:
            text = raw.strip('"')
    
    # Get tables
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
    
    return text, tables

def _scrape_click_tab(url, tab_label, wait=3):
    """Re-open a page, click a tab button by label, and return (text, tables).
    Used for banks like Elebank where USD rates require clicking a tab.
    Uses snapshot to find the button ref for reliable clicking.
    """
    run_browser('agent-browser close', timeout=5)
    time.sleep(2)
    
    result = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
    if not result:
        return None, None
    
    time.sleep(wait)
    
    # Use snapshot to find the tab button ref
    clicked = False
    snap = run_browser('agent-browser snapshot -i --json', timeout=10)
    if snap:
        try:
            snap_data = json.loads(snap)
            # Handle both formats: {"data":{"refs":{...}}} or [{...}]
            refs = None
            if isinstance(snap_data, dict):
                data = snap_data.get('data', snap_data)
                refs = data.get('refs', None)
            
            if isinstance(refs, dict):
                # refs is a dict like {"e10": {"name": "美元", "role": "button"}}
                for ref_id, elem in refs.items():
                    name = elem.get('name', '')
                    role = elem.get('role', '')
                    if name == tab_label and role == 'button':
                        click_result = run_browser(f'agent-browser click @{ref_id}', timeout=10)
                        if click_result:
                            clicked = True
                            logger.info(f'  Clicked tab @{ref_id} ({tab_label})')
                        break
            elif isinstance(refs, list):
                for elem in refs:
                    if tab_label in elem.get('name', '') or tab_label in elem.get('text', ''):
                        ref = elem.get('ref')
                        if ref:
                            click_result = run_browser(f'agent-browser click {ref}', timeout=10)
                            if click_result:
                                clicked = True
                            break
        except Exception as e:
            logger.warning(f'  Tab click snapshot parse error: {e}')
    
    if not clicked:
        # Last resort: try find text
        run_browser(f'agent-browser find text "{tab_label}" click', timeout=10)
    
    time.sleep(wait)
    
    text, tables = _extract_text_tables()
    
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
        for period in ['1w', '1m', '2m', '3m', '6m', '12m']:
            if bank[currency][period]['rate'] is not None:
                if bank[currency][period].get('source') != 'bank':
                    bank[currency][period]['source'] = 'moneyhero'
                    note = bank[currency][period].get('note', '')
                    if note and not note.endswith('*'):
                        bank[currency][period]['note'] = note + ' *'
                    elif not note:
                        bank[currency][period]['note'] = '*'

# UHK (ulifestyle) second source
UHK_URL = 'https://hk.ulifestyle.com.hk/topic/detail/20053976/%E9%A6%99%E6%B8%AF%E9%8A%80%E8%A1%8C%E6%B8%AF%E5%85%83%E5%AE%9A%E6%9C%9F%E5%AD%98%E6%AC%BE%E5%88%A9%E7%8E%87%E6%AF%94%E8%BC%83-%E6%9C%80%E6%96%B0%E6%B8%AF%E5%85%83%E5%AE%9A%E6%9C%9F%E9%AB%98%E6%81%AF%E4%B9%8B%E9%81%B8-%E6%AF%8F%E6%97%A5%E6%9B%B4%E6%96%B0/1'

# Bank name aliases for matching UHK text to our bank names
UHK_NAME_MAP = {
    '滙豐': '滙豐銀行',
    '恒生': '恒生銀行',
    '中銀': '中銀香港',
    '渣打': '渣打銀行',
    '星展': '星展銀行',
    '東亞': '東亞銀行',
    '富邦': '富邦銀行',
    '工銀': '工銀亞洲',
    '創興': '創興銀行',
    '大眾': '大眾銀行',
    '中信': '中信銀行（國際）',
    '花旗': '花旗銀行',
    '建設銀行': '建設銀行',
    '南洋': '南洋商業銀行',
    '招商永隆': '招商永隆',
    '永隆': '招商永隆',
    'ZA': '眾安銀行',
    '天星': '象象銀行',
    'PAO': '平安數字銀行',
    '平安': '平安數字銀行',
    '富融': '富融銀行',
    'Mox': 'Mox Bank',
}

def _scrape_uhk():
    """Scrape UHK (ulifestyle) for HKD deposit rates as second source."""
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', '20', UHK_URL],
            capture_output=True, timeout=25
        )
        html = r.stdout.decode('utf-8', errors='ignore')
        if len(html) < 500:
            return {}
    except Exception as e:
        logger.warning(f'UHK fetch failed: {e}')
        return {}

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'\s+', ' ', text)

    # Skip TOC - actual content starts after this marker
    content_start = text.find('以下為你整理')
    if content_start < 0:
        content_start = 0
    content = text[content_start:]

    uhk_rates = {}

    for alias, bank_name in UHK_NAME_MAP.items():
        idx = content.find(alias)
        if idx < 0:
            continue
        section = content[idx:idx + 1500]
        rates = {}
        for period, patterns in [
            ('1m', [r'1個月[^0-9]*(\d+\.\d+)%', r'一個月[^0-9]*(\d+\.\d+)%']),
            ('3m', [r'3個月[^0-9]*(\d+\.\d+)%', r'三個月[^0-9]*(\d+\.\d+)%']),
            ('6m', [r'6個月[^0-9]*(\d+\.\d+)%', r'六個月[^0-9]*(\d+\.\d+)%']),
            ('12m', [r'12個月[^0-9]*(\d+\.\d+)%', r'十二個月[^0-9]*(\d+\.\d+)%']),
        ]:
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    rates[period] = float(m.group(1))
                    break
        if rates:
            if bank_name not in uhk_rates:
                uhk_rates[bank_name] = {}
            uhk_rates[bank_name].update(rates)

    logger.info(f'UHK second source: found {len(uhk_rates)} banks')
    return uhk_rates

def _apply_uhk_fallback(bank, uhk_rates):
    """Apply UHK rates to a bank that failed bank website scrape.
    Only updates if the bank has data in UHK."""
    bank_name = bank['name']
    if bank_name not in uhk_rates:
        return False
    
    uhk = uhk_rates[bank_name]
    updated = False
    for period in ['1m', '3m', '6m', '12m']:
        if period in uhk:
            bank['hkd'][period] = {
                'rate': uhk[period],
                'min_deposit': bank['hkd'][period].get('min_deposit'),
                'note': 'UHK 港生活',
                'source': 'uhk',
            }
            updated = True
    return updated

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
    
    # Scrape UHK as second source (lazy - only if needed)
    uhk_rates = None
    
    def get_uhk_rates():
        nonlocal uhk_rates
        if uhk_rates is None:
            uhk_rates = _scrape_uhk()
        return uhk_rates
    
    for bank in banks:
        bank_name = bank['name']
        parser_key = name_to_key.get(bank_name)
        
        if not parser_key:
            logger.info(f"  ⚠️ {bank_name}: No config, using MoneyHero")
            mark_moneyhero(bank)
            continue
        
        cfg = BANK_CONFIG[parser_key]
        url = cfg['url']
        
        # Skip scrape if configured (e.g. rates only in app, blocked by Cloudflare)
        if cfg.get('skip_scrape'):
            # Try UHK first, then keep existing data
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                logger.info(f"  [{parser_key}] {bank_name} using UHK second source")
            else:
                logger.info(f"  [{parser_key}] Skipping {bank_name}, keeping existing data")
            continue
        
        # Load parser
        parse_fn = load_parser(parser_key)
        
        if parse_fn:
            # This bank has a dedicated parser
            logger.info(f"  [{parser_key}] Parsing {bank_name}...")
            
            needs_tables = cfg.get('needs_tables', False)
            cloudflare_bypass = cfg.get('cloudflare_bypass', False)
            text, tables = scrape_page(url, cloudflare_bypass=cloudflare_bypass)
            
            if text is None and tables is None:
                logger.warning(f"  ✗ Failed to scrape {bank_name}")
                if _apply_uhk_fallback(bank, get_uhk_rates()):
                    logger.info(f"  → {bank_name} using UHK second source")
                else:
                    failed_banks.append(bank_name)
                    mark_moneyhero(bank)
                continue
            
            try:
                result = parse_fn(text, tables)
            except Exception as e:
                logger.warning(f"  ✗ Parser error for {bank_name}: {e}")
                if _apply_uhk_fallback(bank, get_uhk_rates()):
                    logger.info(f"  → {bank_name} using UHK second source")
                else:
                    failed_banks.append(bank_name)
                    mark_moneyhero(bank)
                continue
            
            # If bank has a USD tab to click, scrape USD rates separately
            usd_tab_label = cfg.get('usd_tab')
            if usd_tab_label and result is not None:
                usd_text, usd_tables = _scrape_click_tab(url, usd_tab_label)
                if usd_text or usd_tables:
                    try:
                        usd_result = parse_fn(usd_text, usd_tables)
                        if usd_result and 'usd' in usd_result:
                            result['usd'] = usd_result['usd']
                            logger.info(f"  ✓ Got USD rates from tab for {bank_name}")
                        else:
                            logger.warning(f"  ⚠️ USD tab scraped but parser returned no USD data for {bank_name}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ USD tab parse error for {bank_name}: {e}")
                else:
                    logger.warning(f"  ⚠️ Failed to scrape USD tab for {bank_name}")
            
            if result:
                note = result.get('note', f'從{bank_name}官網提取')
                for currency in ['hkd', 'usd']:
                    if currency in result:
                        for period in ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']:
                            if period in result[currency]:
                                val = result[currency][period]
                                # Support both float and dict (with new_funds)
                                if isinstance(val, dict):
                                    rate = val.get('rate')
                                    new_funds = val.get('new_funds')
                                    any_funds_rate = val.get('any_funds_rate')
                                else:
                                    rate = val
                                    # Preserve existing new_funds from rates.json
                                    new_funds = bank[currency].get(period, {}).get('new_funds')
                                    any_funds_rate = bank[currency].get(period, {}).get('any_funds_rate')
                                bank[currency][period] = {
                                    'rate': rate,
                                    'min_deposit': bank[currency].get(period, {}).get('min_deposit'),
                                    'note': note,
                                    'source': 'bank',
                                }
                                if new_funds is not None:
                                    bank[currency][period]['new_funds'] = new_funds
                                elif 'new_funds' not in bank[currency][period]:
                                    bank[currency][period]['new_funds'] = None
                                if any_funds_rate is not None:
                                    bank[currency][period]['any_funds_rate'] = any_funds_rate
                logger.info(f"  ✓ Parsed {bank_name}: {result}")
                parsed_count += 1
            else:
                logger.warning(f"  ⚠️ Parser returned None for {bank_name}")
                if _apply_uhk_fallback(bank, get_uhk_rates()):
                    logger.info(f"  → {bank_name} using UHK second source")
                else:
                    failed_banks.append(bank_name)
                    mark_moneyhero(bank)
        else:
            # No parser — just scrape and mark source
            logger.info(f"  [{parser_key}] No parser for {bank_name}, scraping text only...")
            text, _ = scrape_page(url)
            
            if text:
                logger.info(f"  ✓ Got data from {bank_name} (no parser, source marked)")
                for currency in ['hkd', 'usd']:
                    for period in ['1w', '1m', '2m', '3m', '6m', '12m']:
                        if bank[currency][period]['rate'] is not None:
                            bank[currency][period]['source'] = 'bank'
                scraped_count += 1
            else:
                logger.warning(f"  ✗ Failed to scrape {bank_name}")
                if _apply_uhk_fallback(bank, get_uhk_rates()):
                    logger.info(f"  → {bank_name} using UHK second source")
                else:
                    failed_banks.append(bank_name)
                    mark_moneyhero(bank)
    
    # Update metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / UHK港生活'

    # Apply bank-level new_funds defaults
    # For banks where parser doesn't return new_funds, use the default map
    NF_DEFAULTS = {
        '滙豐銀行': True,
        '中銀香港': True,
        '恒生銀行': True,
        '渣打銀行': True,
        '工銀亞洲': False,
        '東亞銀行': False,
        '中信銀行（國際）': True,
        '星展銀行': True,
        '交通銀行': True,
        '上海商業銀行': False,
        '大眾銀行': False,
        '招商永隆': False,
        '創興銀行': False,
        '富融銀行': False,
        '象象銀行': False,
        '眾安銀行': False,
        '平安數字銀行': False,
        '匯立銀行': False,
        '理慧銀行': False,
        '螞蟻銀行': False,
        '集友銀行': True,
    }
    for bank in data['banks']:
        nf_default = NF_DEFAULTS.get(bank['name'])
        if nf_default is not None:
            for currency in ['hkd', 'usd']:
                if currency in bank:
                    for period in bank[currency]:
                        entry = bank[currency][period]
                        if isinstance(entry, dict) and entry.get('rate') is not None:
                            if entry.get('new_funds') is None:
                                entry['new_funds'] = nf_default
    
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
    
    # Send Telegram notification
    _send_telegram_summary(parsed_count, scraped_count, failed_banks)
    
    return True


def _send_telegram_summary(parsed_count, scraped_count, failed_banks):
    """Send a Telegram message with the update results."""
    try:
        now = datetime.now(HKT).strftime('%Y-%m-%d %H:%M')
        msg = f"🦆 食息鴨利率更新 ({now})\n"
        msg += f"✅ 成功解析: {parsed_count} | 標記來源: {scraped_count}\n"
        if failed_banks:
            msg += f"\n❌ 更新失敗 ({len(failed_banks)}):\n"
            for name in failed_banks:
                msg += f"  • {name}\n"
        else:
            msg += "\n🎉 全部銀行更新成功！"
        
        cmd = [
            '/home/freet/.npm-global/bin/openclaw', 'message', 'send',
            '-t', '885017126',
            '--channel', 'telegram',
            '-m', msg
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            logger.warning(f'Telegram send failed: {r.stderr.strip()}')
        else:
            logger.info('Telegram notification sent')
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")


def main():
    try:
        success = update_rates()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
