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

提取方式：
1. 首先嘗試 regex parser（scripts/parsers/<bank_key>.py）
2. 若 parser 失敗或返回 None，使用 LLM（zai/glm-4.7）理解原始數據並提取利率
3. 若都失敗，使用 UHK/MoneyHero 後備
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
# Bank URL config
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
        'url': 'https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo#exist_fund',
        'cloudflare_bypass': True,
        'get_html': True,
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
        'skip_scrape': True,
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
        'usd_tab': '美元',
    },
    'za': {
        'name': '眾安銀行',
        'url': 'https://bank.za.group/',
        'skip_scrape': True,
    },
    'pao': {
        'name': '平安數字銀行',
        'url': 'https://www.pingandb.com/tc/retail-td-newfund.html',
        'cloudflare_bypass': True,
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
    },
}

# ============================================================
# Scratch dir: save raw data when parser fails for manual/agent extraction
# ============================================================
SCRATCH_DIR = os.path.join(DATA_DIR, '_scratch')

def save_scraped_data(bank_key, bank_name, url, text, tables, html):
    """Save scraped raw data to scratch dir for later extraction."""
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    data = {
        'bank_key': bank_key,
        'bank_name': bank_name,
        'url': url,
        'scraped_at': datetime.now(HKT).isoformat(),
        'text': text or '',
        'tables': tables or [],
        'html': html or '',
    }
    filepath = os.path.join(SCRATCH_DIR, f'{bank_key}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f'  📄 Saved raw data to {filepath}')



# ============================================================
# Utility functions (scraping, browser)
# ============================================================

def run_browser(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            out = re.sub(r'\x1b\[[0-9;]*m', '', r.stdout).strip()
            return out if out else None
        return None
    except Exception as e:
        logger.warning(f"agent-browser error: {e}")
        return None

def scrape_page(url, wait=5, cloudflare_bypass=False, get_html=False):
    run_browser('agent-browser close', timeout=5)
    time.sleep(2)
    
    if cloudflare_bypass:
        run_browser(
            'agent-browser set headers \'{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}\'',
            timeout=10
        )
    
    result = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
    if not result:
        return None, None, None
    
    time.sleep(wait)
    return _extract_text_tables(get_html=get_html)

def _extract_text_tables(get_html=False):
    raw = run_browser('agent-browser eval "document.body.innerText.substring(0, 8000)"', timeout=10)
    text = None
    if raw:
        try:
            text = json.loads(raw)
        except:
            text = raw.strip('"')
    
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
    
    html = None
    if get_html:
        raw_h = run_browser('agent-browser eval "document.body.innerHTML.substring(0, 30000)"', timeout=10)
        if raw_h:
            try:
                html = json.loads(raw_h)
            except:
                html = raw_h.strip('"')
    
    return text, tables, html

def _scrape_click_tab(url, tab_label, wait=3):
    run_browser('agent-browser close', timeout=5)
    time.sleep(2)
    
    result = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
    if not result:
        return None, None, None
    
    time.sleep(wait)
    
    clicked = False
    snap = run_browser('agent-browser snapshot -i --json', timeout=10)
    if snap:
        try:
            snap_data = json.loads(snap)
            refs = None
            if isinstance(snap_data, dict):
                data = snap_data.get('data', snap_data)
                refs = data.get('refs', None)
            if isinstance(refs, dict):
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
                            run_browser(f'agent-browser click {ref}', timeout=10)
                            clicked = True
                        break
        except Exception as e:
            logger.warning(f'  Tab click error: {e}')
    
    if not clicked:
        run_browser(f'agent-browser find text "{tab_label}" click', timeout=10)
    
    time.sleep(wait)
    text, tables, html = _extract_text_tables()
    run_browser('agent-browser close', timeout=5)
    time.sleep(1)
    return text, tables, html

def load_parser(parser_key):
    try:
        mod = importlib.import_module(f'parsers.{parser_key}')
        return mod.parse
    except ImportError:
        return None

def mark_moneyhero(bank):
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

# ============================================================
# UHK second source
# ============================================================
UHK_URL = 'https://hk.ulifestyle.com.hk/topic/detail/20053976/'

UHK_NAME_MAP = {
    '滙豐': '滙豐銀行', '恒生': '恒生銀行', '中銀': '中銀香港',
    '渣打': '渣打銀行', '星展': '星展銀行', '東亞': '東亞銀行',
    '富邦': '富邦銀行', '工銀': '工銀亞洲', '創興': '創興銀行',
    '大眾': '大眾銀行', '中信': '中信銀行（國際）',
    '招商永隆': '招商永隆', '永隆': '招商永隆',
    'ZA': '眾安銀行', '天星': '象象銀行', 'PAO': '平安數字銀行',
    '平安': '平安數字銀行', '富融': '富融銀行',
}

def _scrape_uhk():
    try:
        r = subprocess.run(['curl', '-sL', '--max-time', '20', UHK_URL], capture_output=True, timeout=25)
        html = r.stdout.decode('utf-8', errors='ignore')
        if len(html) < 500:
            return {}
    except Exception as e:
        logger.warning(f'UHK fetch failed: {e}')
        return {}

    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'\s+', ' ', text)
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
            ('1m', [r'1個月[^0-9]*(\d+\.\d+)%']),
            ('3m', [r'3個月[^0-9]*(\d+\.\d+)%']),
            ('6m', [r'6個月[^0-9]*(\d+\.\d+)%']),
            ('12m', [r'12個月[^0-9]*(\d+\.\d+)%']),
        ]:
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    rates[period] = float(m.group(1))
                    break
        if rates:
            uhk_rates.setdefault(bank_name, {}).update(rates)

    logger.info(f'UHK second source: found {len(uhk_rates)} banks')
    return uhk_rates

def _apply_uhk_fallback(bank, uhk_rates):
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


# ============================================================
# Main update logic
# ============================================================

def update_rates():
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
    
    name_to_key = {cfg['name']: key for key, cfg in BANK_CONFIG.items()}
    
    parsed_count = 0
    scraped_count = 0
    needs_extraction = []  # banks that scraped but parser failed
    failed_banks = []
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
            mark_moneyhero(bank)
            continue
        
        cfg = BANK_CONFIG[parser_key]
        url = cfg['url']
        
        if cfg.get('skip_scrape'):
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                logger.info(f"  [{parser_key}] {bank_name} using UHK second source")
            continue
        
        # --- Phase 1: Scrape raw data ---
        cloudflare_bypass = cfg.get('cloudflare_bypass', False)
        get_html = cfg.get('get_html', False)
        text, tables, html = scrape_page(url, cloudflare_bypass=cloudflare_bypass, get_html=get_html)
        
        if text is None and tables is None:
            logger.warning(f"  [{parser_key}] ✗ Failed to scrape {bank_name}")
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                logger.info(f"  → {bank_name} using UHK second source")
            else:
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
            continue
        
        # --- Phase 2: Try regex parser ---
        result = None
        parse_fn = load_parser(parser_key)
        
        if parse_fn:
            try:
                result = parse_fn(text, tables, html=html)
            except Exception as e:
                logger.warning(f"  [{parser_key}] Parser error for {bank_name}: {e}")
        
        # USD tab handling for parsers that got HKD but not USD
        usd_tab_label = cfg.get('usd_tab')
        if usd_tab_label and result is not None and 'usd' not in result:
            usd_text, usd_tables, usd_html = _scrape_click_tab(url, usd_tab_label)
            if usd_text or usd_tables:
                if parse_fn:
                    try:
                        usd_result = parse_fn(usd_text, usd_tables, html=usd_html)
                        if usd_result and 'usd' in usd_result:
                            result['usd'] = usd_result['usd']
                            logger.info(f"  ✓ Got USD rates from tab for {bank_name}")
                    except Exception:
                        pass
        
        # --- Phase 3: Apply or save for extraction ---
        if result:
            _apply_parsed_rates(bank, result, bank_name)
            logger.info(f"  [{parser_key}] ✓ Parsed {bank_name}")
            parsed_count += 1
        else:
            # Parser failed — save raw data for manual/agent extraction
            save_scraped_data(parser_key, bank_name, url, text, tables, html)
            needs_extraction.append(bank_name)
            logger.info(f"  [{parser_key}] ⏳ Parser failed, saved raw data for {bank_name}")
            
            # Apply UHK fallback for now
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                logger.info(f"  → {bank_name} using UHK fallback (pending extraction)")
            else:
                # Just mark scraped
                for currency in ['hkd', 'usd']:
                    for period in ['1w', '1m', '2m', '3m', '6m', '12m']:
                        if bank[currency][period]['rate'] is not None:
                            bank[currency][period]['source'] = 'bank'
                scraped_count += 1
    
    # Metadata
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / UHK港生活'
    
    # new_funds defaults
    NF_DEFAULTS = {
        '滙豐銀行': True, '中銀香港': True, '恒生銀行': True,
        '渣打銀行': True, '工銀亞洲': False, '東亞銀行': False,
        '中信銀行（國際）': True, '星展銀行': True, '交通銀行': True,
        '上海商業銀行': False, '大眾銀行': False, '招商永隆': False,
        '創興銀行': False, '富融銀行': False, '象象銀行': False,
        '眾安銀行': False, '平安數字銀行': True, '匯立銀行': False,
        '理慧銀行': False, '螞蟻銀行': False, '集友銀行': True,
    }
    for bank in data['banks']:
        nf = NF_DEFAULTS.get(bank['name'])
        if nf is not None:
            for currency in ['hkd', 'usd']:
                if currency in bank:
                    for period in bank[currency]:
                        entry = bank[currency][period]
                        if isinstance(entry, dict) and entry.get('rate') is not None and entry.get('new_funds') is None:
                            entry['new_funds'] = nf
    
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info("=" * 50)
    logger.info(f"Update complete:")
    logger.info(f"  Parsed (regex): {parsed_count}")
    logger.info(f"  Needs extraction: {len(needs_extraction)}")
    logger.info(f"  Scraped (no parser): {scraped_count}")
    logger.info(f"  Failed: {len(failed_banks)}")
    if needs_extraction:
        logger.info(f"  Pending extraction: {', '.join(needs_extraction)}")
    if failed_banks:
        logger.info(f"  Failed banks: {', '.join(failed_banks)}")
    logger.info(f"Last updated: {data['last_updated']}")
    logger.info("=" * 50)
    
    _send_telegram_summary(parsed_count, needs_extraction, scraped_count, failed_banks)
    return True


def _apply_parsed_rates(bank, result, bank_name):
    """Apply parsed rates to bank data structure."""
    note = result.get('note', f'從{bank_name}官網提取')
    for currency in ['hkd', 'usd']:
        if currency not in result:
            continue
        curr_note = result.get(f'{currency}_note', note)
        for period in ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']:
            if period not in result[currency]:
                continue
            val = result[currency][period]
            if isinstance(val, dict):
                rate = val.get('rate')
                new_funds = val.get('new_funds')
                any_funds_rate = val.get('any_funds_rate')
            else:
                rate = val
                new_funds = bank[currency].get(period, {}).get('new_funds')
                any_funds_rate = bank[currency].get(period, {}).get('any_funds_rate')
            bank[currency][period] = {
                'rate': rate,
                'min_deposit': bank[currency].get(period, {}).get('min_deposit'),
                'note': curr_note,
                'source': 'bank',
            }
            if new_funds is not None:
                bank[currency][period]['new_funds'] = new_funds
            elif 'new_funds' not in bank[currency][period]:
                bank[currency][period]['new_funds'] = None
            if any_funds_rate is not None:
                bank[currency][period]['any_funds_rate'] = any_funds_rate


def _send_telegram_summary(parsed_count, needs_extraction, scraped_count, failed_banks):
    try:
        now = datetime.now(HKT).strftime('%Y-%m-%d %H:%M')
        msg = f"🦆 食息鴨利率更新 ({now})\n"
        msg += f"✅ 成功: {parsed_count} | ⏳ 待提取: {len(needs_extraction)} | 📄 標記: {scraped_count}\n"
        if needs_extraction:
            msg += f"\n⏳ 需要 Levie 提取 ({len(needs_extraction)}):\n"
            for name in needs_extraction:
                msg += f"  • {name}\n"
        if failed_banks:
            msg += f"\n❌ 失敗 ({len(failed_banks)}):\n"
            for name in failed_banks:
                msg += f"  • {name}\n"
        if not needs_extraction and not failed_banks:
            msg += "\n🎉 全部銀行更新成功！"
        
        cmd = [
            '/home/freet/.npm-global/bin/openclaw', 'message', 'send',
            '-t', '885017126', '--channel', 'telegram', '-m', msg
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            logger.warning(f'Telegram send failed: {r.stderr.strip()}')
        else:
            logger.info('Telegram notification sent')
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def main():
    try:
        return 0 if update_rates() else 1
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
