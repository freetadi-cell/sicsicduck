#!/usr/bin/env python3
"""
香港銀行定期存款利率自動更新腳本
以銀行官網為第一數據來源，HKET（香港經濟日報）作為補充數據來源

每日 8:30 由 cron 執行

數據結構：
- 幣種：hkd, usd, cny（人民幣）
- 第一類條件（fund_type）：new_funds（新資金）/ existing_funds（現有資金）
- 第二類條件（conditions）：new_account（開立新戶口）/ exchange（兌換）/ upgrade_wealth（提升至理財戶）
- conditions 為陣列，可多選

提取方式：
1. 首先嘗試銀行官網 regex parser（scripts/parsers/<bank_key>.py）
2. 若官網 parser 失敗或部分年期缺失，用 HKET 文章補充缺失年期
3. 若都失敗，使用 UHK 後備
"""

import json
import os
import re
import logging
import importlib
from datetime import datetime, timezone, timedelta, date
import subprocess
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HKT = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')
PARSERS_DIR = os.path.join(SCRIPT_DIR, 'parsers')

ALL_CURRENCIES = ['hkd', 'usd', 'cny']
ALL_PERIODS = ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']

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
        'url': 'https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo',
        'cloudflare_bypass': True,
        'get_html': True,
        'wait': 10,
    },
    'fubon': {
        'name': '富邦銀行',
        'url': 'https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html',
    },
    'icbc': {
        'name': '工銀亞洲',
        'url': 'https://www.icbcasia.com/hk/tc/personal/latest-promotion/new-funds-time-deposit.html',
    },
    'bea': {
        'name': '東亞銀行',
        'url': 'https://www.hkbea.com/html/tc/bea-personal-banking-supremeGold-welcome-offer.html',
    },
    'cncbi': {
        'name': '中信銀行（國際）',
        'url': 'https://www.cncbinternational.com/rate-table/time_deposit_rate_tc.html',
        'cny_url': 'https://www.cncbinternational.com/rate-table/time_deposit_rate_tc.html',
    },
    'ncb': {
        'name': '南洋商業銀行',
        'url': 'https://www.ncbinfo.com/tc/content/deposit',
        'skip_scrape': True,
    },
    'bocomm': {
        'name': '交通銀行',
        'url': 'https://www.bankcomm.com.hk/hk/shtml/hk/tw/2005155/2005178/2005179/list.shtml',
        'skip_scrape': True,
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
        'cny_url': 'https://www.cmbwinglungbank.com/ibanking/CnCoFiiDepratDsp.jsp',
    },
    'chbank': {
        'name': '創興銀行',
        'url': 'https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml',
        'needs_tables': True,
    },
    'fusion': {
        'name': '富融銀行',
        'url': 'https://www.fusionbank.com/',
        'skip_scrape': True,
    },
    'airstar': {
        'name': '象象銀行',
        'url': 'https://www.elebank.com/zh-hk/hkprime.html',
        'usd_tab': '美元',
    },
    'za': {
        'name': '眾安銀行',
        'url': 'https://bank.za.group/',
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
        'skip_scrape': True,
    },
    'chiyu': {
        'name': '集友銀行',
        'url': 'https://www.chiyubank.com/cyb/index/zxxx/20230523/index.shtml',
    },
}

# ============================================================
# HKET articles config (香港經濟日報 — 主要資訊來源)
# ============================================================
HKET_ARTICLES = {
    'hsbc': {
        'article_id': '3909928',
    },
    'bochk': {
        'article_id': '3909868',
    },
    'hangseng': {
        'article_id': '3909885',
    },
    'sc': {
        'article_id': '3909906',
    },
    'dbs': {
        'article_id': '3909888',
    },
    'fubon': {
        'article_id': '3909896',
    },
    'icbc': {
        'article_id': '3909836',
    },
    'bea': {
        'article_id': '3909860',
    },
    'cncbi': {
        'article_id': '3909875',
    },
    'ncb': {
        'article_id': '3909866',
    },
    'bocomm': {
        'article_id': '3909871',
    },
    'shacom': {
        'article_id': '3909825',
    },
    'publicbank': {
        'article_id': '3909827',
    },
    'winglung': {
        'article_id': '3909844',
    },
    'chbank': {
        'article_id': '3909893',
    },
    'fusion': {
        'article_id': '3909899',
    },
    'airstar': {
        'article_id': '3909842',
    },
    'za': {
        'article_id': '3909890',
    },
    'pao': {
        'article_id': '3909822',
    },
    'welab': {
        'article_id': '3909925',
    },
    'livi': {
        'article_id': '3909817',
    },
    'ant': {
        'article_id': '3909930',
    },
    'chiyu': {
        'article_id': '3909922',
    },
}

# ============================================================
# HKET CNY article config (人民幣綜合文章)
# ============================================================
HKET_CNY_ARTICLE = {
    'article_id': '4143776',  # 人民幣定期存款｜6月份最高21厘！高盛指升值預期增強 料未來1年升4%
}

# Map bank names mentioned in CNY article to our bank keys
CNY_NAME_TO_KEY = {
    '中銀': 'bochk', '中銀香港': 'bochk',
    '滙豐': 'hsbc', '滙豐銀行': 'hsbc', 'HSBC': 'hsbc',
    '恒生': 'hangseng', '恒生銀行': 'hangseng',
    '渣打': 'sc', '渣打銀行': 'sc',
    '星展': 'dbs', '星展銀行': 'dbs', 'DBS': 'dbs',
    '富邦': 'fubon', '富邦銀行': 'fubon',
    '工銀': 'icbc', '工銀亞洲': 'icbc', '工商銀行': 'icbc',
    '東亞': 'bea', '東亞銀行': 'bea',
    '中信': 'cncbi', '中信銀行': 'cncbi',
    '南商': 'ncb', '南洋商業': 'ncb', '南洋商業銀行': 'ncb',
    '交通': 'bocomm', '交通銀行': 'bocomm', '交銀': 'bocomm',
    '上海商業': 'shacom', '上海商業銀行': 'shacom',
    '大眾': 'publicbank', '大眾銀行': 'publicbank',
    '招商永隆': 'winglung', '永隆': 'winglung',
    '創興': 'chbank', '創興銀行': 'chbank',
    '富融': 'fusion', '富融銀行': 'fusion', 'Fusion': 'fusion',
    '象象': 'airstar', '象象銀行': 'airstar', '天星': 'airstar',
    '眾安': 'za', '眾安銀行': 'za', 'ZA': 'za',
    '平安': 'pao', '平安數字銀行': 'pao', 'PAO': 'pao', 'PAObank': 'pao',
    '匯立': 'welab', '匯立銀行': 'welab', 'WeLab': 'welab',
    '理慧': 'livi', '理慧銀行': 'livi', 'livi': 'livi', 'livibank': 'livi',
    '螞蟻': 'ant', '螞蟻銀行': 'ant', 'Ant': 'ant',
    '集友': 'chiyu', '集友銀行': 'chiyu',
    '建行': 'ccb_asia', '建行亞洲': 'ccb_asia', '建設銀行': 'ccb_asia',
    '大新': 'dahsing', '大新銀行': 'dahsing',
    '花旗': 'citibank', '花旗銀行': 'citibank',
    'OCBC': 'ocbc', '華僑': 'ocbc', '華僑銀行': 'ocbc',
    'Mox': 'mox', 'Mox Bank': 'mox',
}

# ============================================================
# Scratch dir
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
                sdata = snap_data.get('data', snap_data)
                refs = sdata.get('refs', None)
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
    for currency in ALL_CURRENCIES:
        if currency not in bank:
            continue
        for period in ALL_PERIODS:
            if period not in bank[currency]:
                continue
            entry = bank[currency][period]
            if isinstance(entry, dict) and entry.get('rate') is not None:
                if entry.get('source') not in ('bank', 'hket'):
                    entry['source'] = 'moneyhero'
                    note = entry.get('note', '')
                    if note and not note.endswith('*'):
                        entry['note'] = note + ' *'
                    elif not note:
                        entry['note'] = '*'


# ============================================================
# HKET primary source (香港經濟日報)
# ============================================================

def _fetch_hket_article(article_id):
    """Fetch HKET article HTML and return (text, article_date or None).
    Falls back to agent-browser if curl is blocked (403).
    """
    url = f'https://wealth.hket.com/article/{article_id}/'
    text = None
    article_date = None

    # ---- Try curl first ----
    try:
        r = subprocess.run([
            'curl', '-sL', '--max-time', '20',
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            '-H', 'Accept: text/html,application/xhtml+xml',
            '-H', 'Accept-Language: zh-HK,zh;q=0.9,en;q=0.8',
            url
        ], capture_output=True, timeout=25)
        html = r.stdout.decode('utf-8', errors='ignore')
        if html and len(html) >= 500 and '403 ERROR' not in html and 'Request blocked' not in html:
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
    except Exception as e:
        logger.warning(f'  HKET curl failed: {e}')

    # ---- Fallback to agent-browser if curl failed ----
    if text is None or len(text) < 500:
        logger.info(f'  HKET curl failed/blocked for article {article_id}, trying agent-browser')
        try:
            run_browser('agent-browser close', timeout=5)
            time.sleep(1)
            r2 = run_browser(f'agent-browser open "{url}" --timeout 30000', timeout=35)
            if r2:
                time.sleep(5)
                raw = run_browser('agent-browser eval "document.body.innerText.substring(0, 15000)"', timeout=10)
                if raw:
                    try:
                        text = json.loads(raw)
                    except Exception:
                        text = raw.strip('"')
            run_browser('agent-browser close', timeout=5)
            time.sleep(1)
        except Exception as e:
            logger.warning(f'  HKET browser fallback failed: {e}')
            run_browser('agent-browser close', timeout=5)

    if not text or len(text) < 200:
        return None, None

    # ---- Extract article date ----
    # Support: "最後更新：2026/06/04", "最後更新日期︰2026年5月26日",
    #          "更新日期：2026.06.04", "本文最後更新日期︰2026年6月4日"
    article_date = None
    m = re.search(r'(?:最後更新|更新日期|最後更新日期)[：:︰\s]*(\d{4})[/\.年](\d{1,2})[/\.月](\d{1,2})', text)
    if m:
        article_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return text, article_date


def _parse_hket_rates(text):
    """Parse HKET article text into structured rate data.

    Returns dict with structure:
    {
        'hkd': {
            '3m': {'rate': 2.4, 'min_deposit': 10000, 'fund_type': 'new_funds',
                   'conditions': ['new_account'], 'note': '...'},
            ...
        },
        'usd': { ... },
        'cny': { ... },
        'note': '從香港經濟日報提取',
    }

    The parser looks for multiple rate tables in the article, each preceded by
    a section header that describes the conditions (新資金, 珪有資金, 開立新戶口,
    兌換, 提升至理財戶, etc.). It picks the highest rate for each currency/period
    combination.
    """
    if not text:
        return None

    # Find the article body (between first bank name mention and "資料來源")
    body_start = 0
    body_end = len(text)
    src_marker = text.find('資料來源')
    if src_marker > 0:
        body_end = src_marker

    body = text[body_start:body_end]

    # We'll collect all rate entries with their conditions
    # Then pick the highest rate per (currency, period)
    entries = []  # list of (currency, period, rate, min_deposit, fund_type, conditions, note)

    def _detect_conditions(section_text):
        """Detect fund_type and conditions from section text."""
        fund_type = None
        conditions = []

        if re.search(r'新資金', section_text):
            fund_type = 'new_funds'
        elif re.search(r'現有資金|現有客戶|一般資金|existing', section_text, re.IGNORECASE):
            fund_type = 'existing_funds'

        if re.search(r'開[立設].*?新?戶口|開立|電子渠道開立|new.?account', section_text, re.IGNORECASE):
            conditions.append('new_account')
        if re.search(r'兌換|exchange|currency conversion', section_text, re.IGNORECASE):
            conditions.append('exchange')
        if re.search(r'提升.*?理財|升級.*?理財|理財.*?戶口|理財客戶|wealth|premier', section_text, re.IGNORECASE):
            conditions.append('upgrade_wealth')

        return fund_type, conditions

    def _detect_min_deposit(section_text):
        """Detect minimum deposit amount from section text."""
        # Patterns like "1萬元起", "起存額10,000", "存款額2萬元起", "最低存款額"
        patterns = [
            r'(?:起存額|最低存款|存款額|起)\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:萬|元)',
            r'([\d,]+(?:\.\d+)?)\s*萬元(?:起|存款)',
            r'([\d,]+(?:\.\d+)?)\s*元(?:起|存款)',
        ]
        for pat in patterns:
            m = re.search(pat, section_text)
            if m:
                val_str = m.group(1).replace(',', '')
                val = float(val_str)
                if '萬' in section_text[m.start():m.start() + 30]:
                    val *= 10000
                return int(val)
        return None

    # ---- Extract rates per currency section ----
    # HKET articles typically have sections like:
    # "港元定存詳情" / "美元定存詳情" / "人民幣定存詳情"
    # or "港元 存款期 年利率" tables
    # or inline "3個月 2.4厘"

    # Split into currency sections
    currency_sections = {}

    # Try to find explicit currency sections
    for cur_key, cur_labels in [
        ('hkd', ['港元', 'HKD']),
        ('usd', ['美元', 'USD']),
        ('cny', ['人民幣', 'RMB', 'CNY']),
    ]:
        for label in cur_labels:
            # Find section headers mentioning the currency
            idx = body.find(label)
            if idx >= 0:
                # Find the extent of this section
                next_cur = len(body)
                for other_key, other_labels in [('hkd', ['港元', 'HKD']), ('usd', ['美元', 'USD']), ('cny', ['人民幣', 'RMB', 'CNY'])]:
                    if other_key == cur_key:
                        continue
                    for ol in other_labels:
                        oi = body.find(ol, idx + len(label))
                        if oi > 0 and oi < next_cur:
                            next_cur = oi
                section = body[idx:next_cur]
                if cur_key not in currency_sections or len(section) > len(currency_sections[cur_key]):
                    currency_sections[cur_key] = section
                break

    # If no currency sections found, treat whole body as HKD
    if not currency_sections:
        currency_sections['hkd'] = body

    # Parse rates from each currency section
    for cur_key, section in currency_sections.items():
        fund_type, conditions = _detect_conditions(section)
        min_deposit = _detect_min_deposit(section)

        # Look for "存款期 年利率 起存額 條件" style tables
        # Pattern: period + rate in 厘
        for period, patterns in [
            ('1w', [r'(?<!\d)1星期\s*([\d.]+)\s*厘', r'(?<!\d)7天\s*([\d.]+)\s*厘']),
            ('1m', [r'(?<!\d)1個月\s*([\d.]+)\s*厘']),
            ('2m', [r'(?<!\d)2個月\s*([\d.]+)\s*厘']),
            ('3m', [r'(?<!\d)3個月\s*([\d.]+)\s*厘']),
            ('4m', [r'(?<!\d)4個月\s*([\d.]+)\s*厘']),
            ('6m', [r'(?<!\d)6個月\s*([\d.]+)\s*厘']),
            ('9m', [r'(?<!\d)9個月\s*([\d.]+)\s*厘']),
            ('12m', [r'(?<!\d)12個月\s*([\d.]+)\s*厘']),
        ]:
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    rate = float(m.group(1))
                    if rate > 0:
                        # Check if there's a per-row condition near this rate
                        # Look backwards from the rate match for nearby condition text
                        context_start = max(0, m.start() - 100)
                        context = section[context_start:m.end() + 50]
                        row_fund_type, row_conditions = _detect_conditions(context)
                        row_min = _detect_min_deposit(context) or min_deposit

                        entries.append({
                            'currency': cur_key,
                            'period': period,
                            'rate': rate,
                            'min_deposit': row_min,
                            'fund_type': row_fund_type or fund_type,
                            'conditions': row_conditions or conditions,
                        })
                    break  # Found rate for this period, move on

    # Fallback: if currency section splitting missed the rate table
    # (e.g. promotional mentions of other currencies truncate the section),
    # try parsing the full body as a single HKD section
    if not entries:
        logger.debug('  HKET: no rates found in currency sections, trying full-body fallback')
        fund_type, conditions = _detect_conditions(body)
        min_deposit = _detect_min_deposit(body)
        for period, patterns in [
            ('1w', [r'(?<!\d)1星期\s*([\d.]+)\s*厘', r'(?<!\d)7天\s*([\d.]+)\s*厘']),
            ('1m', [r'(?<!\d)1個月\s*([\d.]+)\s*厘']),
            ('2m', [r'(?<!\d)2個月\s*([\d.]+)\s*厘']),
            ('3m', [r'(?<!\d)3個月\s*([\d.]+)\s*厘']),
            ('4m', [r'(?<!\d)4個月\s*([\d.]+)\s*厘']),
            ('6m', [r'(?<!\d)6個月\s*([\d.]+)\s*厘']),
            ('9m', [r'(?<!\d)9個月\s*([\d.]+)\s*厘']),
            ('12m', [r'(?<!\d)12個月\s*([\d.]+)\s*厘']),
        ]:
            for pat in patterns:
                m = re.search(pat, body)
                if m:
                    rate = float(m.group(1))
                    if rate > 0:
                        context_start = max(0, m.start() - 100)
                        context = body[context_start:m.end() + 50]
                        row_fund_type, row_conditions = _detect_conditions(context)
                        row_min = _detect_min_deposit(context) or min_deposit
                        entries.append({
                            'currency': 'hkd',
                            'period': period,
                            'rate': rate,
                            'min_deposit': row_min,
                            'fund_type': row_fund_type or fund_type,
                            'conditions': row_conditions or conditions,
                        })
                    break

    if not entries:
        return None

    # Pick the highest rate per (currency, period)
    best = {}
    for e in entries:
        key = (e['currency'], e['period'])
        if key not in best or e['rate'] > best[key]['rate']:
            best[key] = e

    # Build result structure
    result = {'note': '從香港經濟日報提取'}
    for (cur, period), e in best.items():
        result.setdefault(cur, {})
        result[cur][period] = {
            'rate': e['rate'],
            'min_deposit': e.get('min_deposit'),
            'fund_type': e.get('fund_type'),
            'conditions': e.get('conditions', []),
        }

    # Ensure all currencies present
    for cur in ALL_CURRENCIES:
        if cur not in result:
            result[cur] = {}

    return result


def _hket_get_rates(bank_key, bank_name):
    """Fetch and parse HKET article for a bank.
    Returns (rates_dict, True) if successful, (None, False) otherwise.
    Checks article date is today or yesterday.
    """
    cfg = HKET_ARTICLES.get(bank_key)
    if not cfg:
        return None, False

    text, article_date = _fetch_hket_article(cfg['article_id'])
    if text is None:
        logger.info(f'  [{bank_key}] HKET: fetch failed for {bank_name}')
        return None, False

    # Date check: accept today or yesterday only
    today = date.today()
    yesterday = today - timedelta(days=1)

    if article_date is None:
        logger.info(f'  [{bank_key}] HKET: could not find article date for {bank_name}, skipping')
        return None, False

    if article_date not in (today, yesterday):
        logger.info(f'  [{bank_key}] HKET article last updated {article_date.strftime("%Y/%m/%d")}, not today or yesterday, skipping HKET')
        return None, False

    result = _parse_hket_rates(text)
    if result is None:
        logger.info(f'  [{bank_key}] HKET: could not parse rates for {bank_name}')
        return None, False

    # Log what we found
    found = []
    for cur in ALL_CURRENCIES:
        periods = [p for p, v in result.get(cur, {}).items() if isinstance(v, dict) and v.get('rate')]
        if periods:
            found.append(f'{cur}: {periods}')
    if found:
        logger.info(f'  HKET: found rates for {bank_name}: {", ".join(found)}')
    else:
        logger.info(f'  HKET: no rates found for {bank_name}')
        return None, False

    return result, True


def _generic_cny_parse(text, tables=None):
    """Generic regex parser for CNY (人民幣) time deposit rates.
    
    Strategy: Find the CNY-specific section on the page, bounded by
    currency markers. Only extract rates from within that section.
    
    Returns dict of {period_key: {'rate': float, ...}} or None.
    """
    if not text:
        return None
    
    if not any(kw in text for kw in ['人民幣', 'RMB', 'CNY']):
        return None
    
    # ---- Step 1: Isolate the CNY section ----
    # Strategy: Find the LAST occurrence of 人民幣/RMB/CNY that has rates nearby.
    # This avoids matching a navigation menu mention and focuses on the actual rate table.
    
    # Preferred markers (most specific first)
    cny_start = None
    for marker in ['人民幣定期存款利率', '人民幣定期', '人民幣定存', '人民幣新資金',
                   'RMB Time Deposit']:
        idx = text.rfind(marker)  # Use rfind to get last occurrence
        if idx >= 0:
            cny_start = idx
            break
    
    if cny_start is None:
        # Find the last 人民幣 that's followed by rate-like content (N個月 + digits)
        best_pos = -1
        for m in re.finditer(r'人民幣', text):
            pos = m.start()
            # Check if there's a rate pattern within 200 chars
            after = text[pos:pos+200]
            if re.search(r'\d+\s*(?:個月|个月)\s*[:：]?\s*\d+\.?\d*\s*%', after):
                best_pos = pos
        if best_pos >= 0:
            cny_start = best_pos
        else:
            # Try RMB/CNY
            for marker in ['RMB', 'CNY']:
                idx = text.rfind(marker)
                if idx >= 0:
                    cny_start = idx
                    break
            # Last resort: use the last 人民幣 occurrence
            if cny_start is None:
                positions = [m.start() for m in re.finditer('人民幣', text)]
                if positions:
                    cny_start = max(positions)
    
    if cny_start is None:
        return None
    
    # Find where CNY section ends (next currency section or end of text)
    cny_end = len(text)
    for stop_marker in ['美元定期', '美元存款', '美元1,000', '美元\n', '美元\t',
                        'USD Time Deposit', 'USD\n',
                        '澳元定期', '紐元定期', '英鎊定期', '加元定期',
                        '澳元存款', '歐羅', '歐元',
                        '外匯買賣風險', '人民幣兌換限制', '條款及細則',
                        '聯絡我們', '常見問題', '備註']:
        idx = text.find(stop_marker, cny_start + 3)
        if idx >= 0 and idx < cny_end:
            cny_end = idx
    
    cny_section = text[cny_start:cny_end]
    if len(cny_section) < 10:
        return None
    
    rates = {}
    
    # ---- Step 2: Extract period-rate pairs from CNY section ----
    
    # Pattern A: "N個月 X.XX%" or "N個月\tX.XX%"
    for m in re.finditer(r'(\d+)\s*(?:個月|个月)\s*[:：]?\s*(\d+\.?\d*)\s*%', cny_section):
        n = int(m.group(1))
        pk = f'{n}m' if f'{n}m' in ALL_PERIODS else None
        if pk:
            rate = float(m.group(2))
            if rate > 0:
                rates[pk] = {'rate': rate, 'note': '從銀行官網提取'}
    
    # Pattern B: Chinese period names
    period_map = {'一個月': '1m', '二個月': '2m', '兩個月': '2m', '三個月': '3m',
                  '四個月': '4m', '六個月': '6m', '九個月': '9m', '十二個月': '12m',
                  '一个月': '1m', '二个月': '2m', '三个月': '3m',
                  '四个月': '4m', '六个月': '6m', '九个月': '9m', '十二个月': '12m',
                  '1個月': '1m', '2個月': '2m', '3個月': '3m', '4個月': '4m',
                  '6個月': '6m', '9個月': '9m', '12個月': '12m'}
    
    for cn, pk in period_map.items():
        if pk in rates:
            continue
        m = re.search(rf'{cn}\s*[:：]?\s*(\d+\.?\d*)\s*%', cny_section)
        if m:
            rate = float(m.group(1))
            if rate > 0:
                rates[pk] = {'rate': rate, 'note': '從銀行官網提取'}
    
    # Pattern C: English "N months X.XX%" (after RMB/CNY marker)
    for m in re.finditer(r'(\d+)\s*months?\s*[:：]?\s*(\d+\.?\d*)\s*%', cny_section):
        n = int(m.group(1))
        pk = f'{n}m' if f'{n}m' in ALL_PERIODS else None
        if pk:
            rate = float(m.group(2))
            if rate > 0:
                rates[pk] = {'rate': rate, 'note': '從銀行官網提取'}
    
    # Pattern D: Short-term "7天" or "1星期" (exchange rates)
    for m in re.finditer(r'(?:7\s*天|1\s*星期|一星期)\s*[:：]?\s*(\d+\.?\d*)\s*%', cny_section):
        rate = float(m.group(1))
        if rate > 0:
            rates['1w'] = {'rate': rate, 'note': '從銀行官網提取（兌換）', 'conditions': ['exchange']}
    
    # Pattern E: Tabular format with column headers
    # e.g. header: 一星期 二星期 一個月 二個月 三個月 六個月 十二個月
    #      data:   0.01%  0.01%  0.10%  0.10%  0.15%  0.25%  0.30%
    # The header may be BEFORE the CNY section, so search the full text
    period_labels = [('一星期', '1w'), ('二星期', '2w'), ('一個月', '1m'), ('1個月', '1m'),
                     ('二個月', '2m'), ('2個月', '2m'), ('三個月', '3m'), ('3個月', '3m'),
                     ('四個月', '4m'), ('4個月', '4m'), ('六個月', '6m'), ('6個月', '6m'),
                     ('九個月', '9m'), ('9個月', '9m'), ('十二個月', '12m'), ('12個月', '12m')]
    
    # Find header line in the broader text context (around the CNY section)
    search_area = text[max(0, cny_start-500):cny_start+len(cny_section)]
    col_periods = []
    for cn, pk in period_labels:
        idx = search_area.find(cn)
        if idx >= 0 and pk not in rates:
            col_periods.append((idx, pk))
    
    if col_periods:
        # Find data in the CNY section: percentage values
        pcts = re.findall(r'(\d+\.\d+)%', cny_section)
        if len(pcts) >= len(col_periods):
            # Take only the first N percentages matching the columns
            # (avoid picking up data from the next currency section)
            for i, (_, pk) in enumerate(col_periods):
                if pk not in rates and pk in ALL_PERIODS and i < len(pcts):
                    rate = float(pcts[i])
                    if rate > 0:
                        rates[pk] = {'rate': rate, 'note': '從銀行官網提取'}
    
    return rates if rates else None




def _hket_get_cny_rates():
    """Fetch and parse HKET CNY overview article for ALL banks.
    Returns dict of {bank_key: {cny: {period: {rate, fund_type, conditions, ...}}}} or empty dict.
    """
    cfg = HKET_CNY_ARTICLE
    text, article_date = _fetch_hket_article(cfg['article_id'])
    if text is None:
        logger.info('  HKET CNY: fetch failed')
        return {}

    today = date.today()
    if article_date is None:
        logger.info('  HKET CNY: could not find article date, attempting parse anyway')
        # Don't skip - still try to parse
    elif (today - article_date).days > 14:
        logger.info(f'  HKET CNY article last updated {article_date.strftime("%Y/%m/%d")}, older than 14 days, skipping')
        return {}

    date_str = article_date.strftime("%Y/%m/%d") if article_date else 'unknown'
    logger.info(f'  HKET CNY: article updated {date_str}, parsing...')

    # Parse the comparison table and inline rate mentions
    # Format 1: "12個月1.5厘（中銀、南商、富融、螞蟻）"
    # Format 2: "3個月（現有客戶）1.5厘（螞蟻、富融）"
    # Format 3: "1個月（兌換資金）6.8厘（平安）"

    bank_cny = {}  # bank_key -> {cny: {period: {rate, fund_type, conditions}}}

    # Pattern: period + optional condition + rate + banks
    # e.g. "12個月1.5厘（中銀、南商、富融、螞蟻）"
    # e.g. "3個月（現有客戶）1.5厘（螞蟻、富融）"
    # e.g. "1星期（兌換資金）21厘（平安）"
    patterns = [
        # period(condition) rate(banks)
        r'(?P<period>\d+個月|\d+星期|\d+天)\s*[（(](?P<cond>[^）)]+)[）)]\s*(?P<rate>[\d.]+)厘[（(](?P<banks>[^）)]+)[）)]',
        # period rate(banks)
        r'(?P<period>\d+個月|\d+星期|\d+天)\s*(?P<rate>[\d.]+)厘[（(](?P<banks>[^）)]+)[）)]',
    ]

    period_map = {
        '1星期': '1w', '7天': '1w', '1個月': '1m', '2個月': '2m',
        '3個月': '3m', '4個月': '4m', '5個月': '5m', '6個月': '6m',
        '9個月': '9m', '12個月': '12m',
    }

    for pat in patterns:
        for m in re.finditer(pat, text):
            period_str = m.group('period')
            period_key = period_map.get(period_str)
            if not period_key:
                continue
            rate = float(m.group('rate'))
            if rate <= 0:
                continue
            banks_str = m.group('banks')
            cond_str = m.groupdict().get('cond', '') or ''

            # Parse conditions
            fund_type = None
            conditions = []
            if '新資金' in cond_str or '新客' in cond_str:
                fund_type = 'new_funds'
            elif '現有' in cond_str:
                fund_type = 'existing_funds'
            if '兌換' in cond_str:
                conditions.append('exchange')
            if '新開' in cond_str or '新戶' in cond_str or '開戶' in cond_str:
                conditions.append('new_account')
                fund_type = 'new_funds'
            if '理財' in cond_str or '貴賓' in cond_str:
                conditions.append('upgrade_wealth')

            # Parse bank names
            bank_names = re.split(r'[、，,]|及|和', banks_str)
            for bn in bank_names:
                bn = bn.strip()
                if not bn:
                    continue
                # Find matching key
                key = None
                for name, k in CNY_NAME_TO_KEY.items():
                    if name in bn or bn in name:
                        key = k
                        break
                if not key:
                    continue

                if key not in bank_cny:
                    bank_cny[key] = {'cny': {}}
                if period_key not in bank_cny[key]['cny']:
                    bank_cny[key]['cny'][period_key] = {
                        'rate': rate,
                        'fund_type': fund_type,
                        'conditions': list(conditions),
                        'note': '從香港經濟日報人民幣文章提取',
                        'source': 'hket',
                    }
                else:
                    # Keep the higher rate
                    if rate > bank_cny[key]['cny'][period_key]['rate']:
                        bank_cny[key]['cny'][period_key]['rate'] = rate
                        bank_cny[key]['cny'][period_key]['fund_type'] = fund_type
                        bank_cny[key]['cny'][period_key]['conditions'] = list(conditions)

    # ---- Phase 2: Parse prose/inline rate mentions ----
    # Parse sentence by sentence for CNY rate data from the article prose.

    def _add_cny_rate(bkey, pk, rate, ft='new_funds', conds=None):
        """Helper to add a CNY rate entry."""
        if not bkey or rate <= 0 or pk not in ALL_PERIODS:
            return
        if bkey not in bank_cny:
            bank_cny[bkey] = {'cny': {}}
        existing = bank_cny[bkey]['cny'].get(pk, {})
        existing_rate = existing.get('rate', 0) if isinstance(existing, dict) else 0
        if rate > existing_rate:
            bank_cny[bkey]['cny'][pk] = {
                'rate': rate,
                'fund_type': ft,
                'conditions': conds or [],
                'note': '從香港經濟日報人民幣文章提取',
                'source': 'hket',
            }

    def _find_bkey(s):
        for name, k in CNY_NAME_TO_KEY.items():
            if name in s or s in name:
                return k
        return None

    # Find the CNY prose section (before the comparison table)
    cny_section_start = text.find('人民幣定期存款最高')
    if cny_section_start < 0:
        cny_section_start = text.find('人民幣定存')
    table_start = text.find('存款期 人民幣定存')
    if table_start < 0:
        table_start = text.find('人民幣定存 VS 港元定存')
    if cny_section_start >= 0:
        if table_start < 0:
            table_start = len(text)
        cny_prose = text[cny_section_start:table_start]
    else:
        cny_prose = ''

    if cny_prose:
        # 1. 平安數字銀行: "7天人民幣定存有21厘、14天有10厘、1個月有6.8厘、3個月有2.5厘"
        rate_list = re.findall(r'(\d+)(天|個月)(?:人民幣定存)?有([\d.]+)厘', cny_prose)
        # Only apply to 平安 if found in the right context
        if '平安數字銀行' in cny_prose and '外幣兌換定存限時優惠' in cny_prose:
            for val, unit, rate_str in rate_list:
                n = int(val)
                if unit == '天':
                    pk = '1w' if n == 7 else None
                else:
                    pk = f'{n}m' if f'{n}m' in ALL_PERIODS else None
                if pk:
                    _add_cny_rate('pao', pk, float(rate_str), conds=['exchange'])

        # 2. 眾安銀行: "眾安銀行也同時設有7天的人民幣兌換定存，年利率達20厘"
        m = re.search(r'眾安銀行.*?(\d+)天.*?人民幣.*?定存.*?年利率達([\d.]+)厘', cny_prose)
        if m:
            pk = '1w' if int(m.group(1)) == 7 else None
            if pk:
                _add_cny_rate('za', pk, float(m.group(2)), conds=['exchange'])

        # 3. 星展銀行: "星展銀行最高，有16厘年利率"
        m = re.search(r'星展銀行.*?有([\d.]+)厘.*?年利率', cny_prose)
        if m:
            _add_cny_rate('dbs', '1w', float(m.group(1)), conds=['exchange'])

        # 4. 南商及富邦: "南商及富邦則分別有13.88厘及12.88厘"
        m = re.search(r'南商.*?富邦.*?分別有([\d.]+)厘.*?([\d.]+)厘', cny_prose)
        if m:
            _add_cny_rate('ncb', '1w', float(m.group(1)), conds=['exchange'])
            _add_cny_rate('fubon', '1w', float(m.group(2)), conds=['exchange'])

        # 5. 滙豐及恒生: "滙豐及恒生都有12厘"
        m = re.search(r'滙豐.*?恒生.*?有([\d.]+)厘', cny_prose)
        if m:
            rate = float(m.group(1))
            _add_cny_rate('hsbc', '1w', rate, conds=['exchange'])
            _add_cny_rate('hangseng', '1w', rate, conds=['exchange'])

        # 6. 中銀香港及渣打: "中銀香港及渣打分別有11.8厘及11厘"
        m = re.search(r'中銀香港.*?渣打.*?分別有([\d.]+)厘.*?([\d.]+)厘', cny_prose)
        if m:
            _add_cny_rate('bochk', '1w', float(m.group(1)), conds=['exchange'])
            _add_cny_rate('sc', '1w', float(m.group(2)), conds=['exchange'])

        # 7. Long-term prose: "12個月人民幣定期存款...提供1.5厘，分別是中銀香港、南商、螞蟻及富融"
        for m in re.finditer(r'(\d+)個月人民幣(?:定期)?存款.*?提供([\d.]+)厘.*?分別是(.+?)(?:，|。|要求)', cny_prose):
            n = int(m.group(1))
            pk = f'{n}m' if f'{n}m' in ALL_PERIODS else None
            if not pk:
                continue
            rate = float(m.group(2))
            banks_str = m.group(3)
            # Check following context for fund type
            ctx = cny_prose[m.end():m.end()+60] if m.end() < len(cny_prose) else ''
            for bp in re.split(r'[、，,]|及|和', banks_str):
                bp = bp.strip()
                bkey = _find_bkey(bp)
                if bkey:
                    # Check if specific bank has different conditions
                    bank_ctx = ctx
                    ft = 'new_funds'
                    if bp in ctx and '毋需' in ctx:
                        ft = 'existing_funds'
                    _add_cny_rate(bkey, pk, rate, ft=ft)

        # 8. "6個月人民幣定存，可留意大新銀行...另螞蟻及富融銀行都有1.5厘"
        for m in re.finditer(r'(\d+)個月人民幣定存.*?可留意([\u4e00-\u9fff]+銀行)', cny_prose):
            n = int(m.group(1))
            pk = f'{n}m' if f'{n}m' in ALL_PERIODS else None
            if not pk:
                continue
            bkey = _find_bkey(m.group(2))
            if bkey:
                rate_m = re.search(r'有([\d.]+)厘', cny_prose[m.start():m.end()])
                if rate_m:
                    _add_cny_rate(bkey, pk, float(rate_m.group(1)))
        # "另螞蟻及富融銀行都有1.5厘"
        for m in re.finditer(r'另(.+?)銀行(?:都)?有([\d.]+)厘', cny_prose):
            rate = float(m.group(2))
            # Find period from earlier in the paragraph
            para_start = cny_prose.rfind('。', 0, m.start())
            if para_start < 0:
                para_start = 0
            pm = re.search(r'(\d+)個月', cny_prose[para_start:m.start()])
            if pm:
                pk = f'{int(pm.group(1))}m'
                if pk in ALL_PERIODS:
                    for bp in re.split(r'[、，,]|及|和', m.group(1)):
                        bp = bp.strip()
                        bkey = _find_bkey(bp)
                        if bkey:
                            _add_cny_rate(bkey, pk, rate, ft='existing_funds')

    found_banks = list(bank_cny.keys())
    if found_banks:
        logger.info(f'  HKET CNY: found rates for {len(found_banks)} banks: {found_banks}')
    else:
        logger.info('  HKET CNY: no bank rates found in article')

    return bank_cny


def _apply_hket_rates(bank, bank_key, bank_name):
    """Try to get rates from HKET and apply them.
    Returns True if rates were applied.
    """
    result, ok = _hket_get_rates(bank_key, bank_name)
    if not ok or result is None:
        return False

    for cur in ALL_CURRENCIES:
        if cur not in result:
            continue
        for period in ALL_PERIODS:
            if period not in result[cur]:
                continue
            val = result[cur][period]
            if not isinstance(val, dict) or val.get('rate') is None:
                continue

            bank[cur][period] = {
                'rate': val['rate'],
                'min_deposit': val.get('min_deposit') or bank[cur].get(period, {}).get('min_deposit'),
                'note': result.get('note', '從香港經濟日報提取'),
                'source': 'hket',
            }
            if val.get('fund_type'):
                bank[cur][period]['fund_type'] = val['fund_type']
            else:
                bank[cur][period]['fund_type'] = None
            if val.get('conditions'):
                bank[cur][period]['conditions'] = val['conditions']
            else:
                bank[cur][period]['conditions'] = []

    return True


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
                'min_deposit': bank['hkd'].get(period, {}).get('min_deposit'),
                'note': 'UHK 港生活',
                'source': 'uhk',
                'fund_type': None,
                'conditions': [],
            }
            updated = True
    return updated


# ============================================================
# Main update logic
# ============================================================

def _ensure_currency_slots(bank):
    """Ensure all currency and period slots exist in bank data."""
    for cur in ALL_CURRENCIES:
        if cur not in bank:
            bank[cur] = {}
        for period in ALL_PERIODS:
            if period not in bank[cur]:
                bank[cur][period] = {
                    'rate': None,
                    'min_deposit': None,
                    'note': None,
                    'source': None,
                    'fund_type': None,
                    'conditions': [],
                }
            else:
                entry = bank[cur][period]
                if isinstance(entry, dict):
                    if 'fund_type' not in entry:
                        entry['fund_type'] = None
                    if 'conditions' not in entry:
                        entry['conditions'] = []
                # Migrate old format (bare value) to dict
                elif isinstance(entry, (int, float)):
                    bank[cur][period] = {
                        'rate': entry,
                        'min_deposit': None,
                        'note': None,
                        'source': None,
                        'fund_type': None,
                        'conditions': [],
                    }


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

    # Ensure all banks have cny currency slots
    for bank in banks:
        _ensure_currency_slots(bank)

    name_to_key = {cfg['name']: key for key, cfg in BANK_CONFIG.items()}

    # ---- Phase 0: Fetch HKET CNY overview article for ALL banks ----
    cny_hket_data = _hket_get_cny_rates()

    verified_same = []
    verified_updated = []   # (bank_name, changes_count)
    unverified = []         # banks that couldn't be verified
    needs_extraction = []
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
            unverified.append(bank_name)
            logger.warning(f"  ✗ {bank_name}: no parser configured")
            continue

        cfg = BANK_CONFIG[parser_key]
        url = cfg['url']
        bank_updated = False

        # ---- Apply HKET CNY data if available ----
        if parser_key and parser_key in cny_hket_data:
            cny_data = cny_hket_data[parser_key].get('cny', {})
            if cny_data:
                for period, val in cny_data.items():
                    if isinstance(val, dict) and val.get('rate'):
                        bank['cny'][period] = {
                            'rate': val['rate'],
                            'min_deposit': bank['cny'].get(period, {}).get('min_deposit'),
                            'note': val.get('note', '從香港經濟日報人民幣文章提取'),
                            'source': 'hket',
                            'fund_type': val.get('fund_type'),
                            'conditions': val.get('conditions', []),
                        }
                cny_periods = [p for p, v in cny_data.items() if isinstance(v, dict) and v.get('rate')]
                if cny_periods:
                    logger.info(f'  [{parser_key}] CNY from HKET overview: {cny_periods}')

        # ---- Phase 1: Bank website scraping (PRIMARY source for HKD/USD) ----
        if cfg.get('skip_scrape'):
            # No website scraping for this bank → try HKET as primary, then UHK
            logger.info(f"  [{parser_key}] {bank_name}: skip_scrape, trying HKET as primary...")
            hket_verified = False
            if parser_key in HKET_ARTICLES:
                hket_result, hket_ok = _hket_get_rates(parser_key, bank_name)
                if hket_ok and hket_result:
                    changed = _compare_rates(bank, hket_result)
                    _apply_result_rates(bank, hket_result, bank_name, source='hket')
                    hket_verified = True
                    if changed:
                        verified_updated.append((bank_name, len(changed)))
                        bank_updated = True
                        logger.info(f"  [{parser_key}] ✓ {bank_name}: HKET rates UPDATED ({len(changed)} changed)")
                    else:
                        verified_same.append(bank_name)
                        logger.info(f"  [{parser_key}] ✓ {bank_name}: HKET rates unchanged (verified)")
            if not hket_verified:
                if _apply_uhk_fallback(bank, get_uhk_rates()):
                    unverified.append(bank_name)
                    logger.info(f"  [{parser_key}] {bank_name}: using UHK fallback (unverified)")
                else:
                    unverified.append(bank_name)
                    mark_moneyhero(bank)
                    logger.warning(f"  [{parser_key}] {bank_name}: no data source available (unverified)")
            continue

        text, tables, html = scrape_page(
            url,
            wait=cfg.get('wait', 5),
            cloudflare_bypass=cfg.get('cloudflare_bypass', False),
            get_html=cfg.get('get_html', False)
        )

        if text is None and tables is None:
            logger.warning(f"  [{parser_key}] ✗ Failed to scrape {bank_name}")
            # Scrape failed → try HKET as fallback, then UHK
            if parser_key in HKET_ARTICLES:
                hket_result, hket_ok = _hket_get_rates(parser_key, bank_name)
                if hket_ok and hket_result:
                    _apply_result_rates(bank, hket_result, bank_name, source='hket')
                    unverified.append(bank_name)
                    logger.info(f"  [{parser_key}] → {bank_name}: scrape failed, using HKET fallback (unverified)")
                    continue
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                unverified.append(bank_name)
                logger.info(f"  → {bank_name} using UHK fallback (unverified)")
            else:
                failed_banks.append(bank_name)
                mark_moneyhero(bank)
                unverified.append(bank_name)
            continue

        # ---- Phase 2: Try regex parser on bank website data ----
        result = None
        parse_fn = load_parser(parser_key)

        if parse_fn:
            try:
                result = parse_fn(text, tables, html=html)
            except Exception as e:
                logger.warning(f"  [{parser_key}] Parser error for {bank_name}: {e}")

        # USD tab handling
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

        # ---- Phase 3: Apply bank website result ----
        if result:
            wrapped = _wrap_parser_result(result, bank_name)
            changed = _compare_rates(bank, wrapped)
            _apply_result_rates(bank, wrapped, bank_name, source='bank')
            if changed:
                verified_updated.append((bank_name, len(changed)))
                bank_updated = True
                logger.info(f"  [{parser_key}] ✓ {bank_name}: bank website rates UPDATED ({len(changed)} changed)")
            else:
                verified_same.append(bank_name)
                logger.info(f"  [{parser_key}] ✓ {bank_name}: bank website rates unchanged (verified)")
        else:
            # Parser failed — save raw data for later extraction
            save_scraped_data(parser_key, bank_name, url, text, tables, html)
            needs_extraction.append(bank_name)
            logger.info(f"  [{parser_key}] ⏳ Parser failed, saved raw data for {bank_name}")

            # Still try UHK as immediate fallback
            if _apply_uhk_fallback(bank, get_uhk_rates()):
                logger.info(f"  → {bank_name} using UHK fallback (pending extraction)")
            else:
                mark_moneyhero(bank)
            unverified.append(bank_name)
            continue  # No bank data to supplement

        # ---- Phase 3.5: CNY bank website fallback ----
        # If CNY rates are still missing after parser + HKET CNY, try generic CNY regex
        # on already-scraped bank website data (or scrape a CNY-specific page)
        cny_missing = [p for p in ALL_PERIODS if bank['cny'].get(p, {}).get('rate') is None]
        if cny_missing:
            # Try generic CNY parse on scraped text first
            if text and '人民幣' in (text or ''):
                cny_generic = _generic_cny_parse(text, tables)
                if cny_generic:
                    applied = []
                    for pk in cny_missing:
                        if pk in cny_generic and cny_generic[pk].get('rate'):
                            bank['cny'][pk] = {
                                'rate': cny_generic[pk]['rate'],
                                'min_deposit': cny_generic[pk].get('min_deposit'),
                                'note': cny_generic[pk].get('note', f'從{bank_name}官網提取'),
                                'source': 'bank',
                                'fund_type': cny_generic[pk].get('fund_type', 'new_funds'),
                                'conditions': cny_generic[pk].get('conditions', []),
                            }
                            applied.append(pk)
                    if applied:
                        logger.info(f'  [{parser_key}] CNY generic fallback: {applied}')
                        cny_missing = [p for p in cny_missing if p not in applied]

            # If still missing and bank has a CNY-specific page, scrape it
            cny_url = cfg.get('cny_url')
            if cny_missing and cny_url:
                logger.info(f'  [{parser_key}] Scraping CNY page: {cny_url}')
                cny_text, cny_tables, cny_html = scrape_page(
                    cny_url,
                    wait=cfg.get('cny_wait', 5),
                    cloudflare_bypass=cfg.get('cloudflare_bypass', False),
                    get_html=False,
                )
                if cny_text:
                    # Try dedicated parser first
                    cny_result = None
                    parse_fn = load_parser(parser_key)
                    if parse_fn:
                        try:
                            cny_result = parse_fn(cny_text, cny_tables, html=cny_html)
                        except Exception:
                            pass
                    if cny_result and 'cny' in cny_result:
                        for pk in cny_missing:
                            val = cny_result['cny'].get(pk)
                            if val and (isinstance(val, dict) and val.get('rate') or isinstance(val, (int, float))):
                                rate = val.get('rate', val) if isinstance(val, dict) else val
                                bank['cny'][pk] = {
                                    'rate': rate,
                                    'min_deposit': val.get('min_deposit') if isinstance(val, dict) else None,
                                    'note': cny_result.get('cny_note', cny_result.get('note', f'從{bank_name}官網提取')),
                                    'source': 'bank',
                                    'fund_type': val.get('fund_type') if isinstance(val, dict) else None,
                                    'conditions': val.get('conditions', []) if isinstance(val, dict) else [],
                                }
                        logger.info(f'  [{parser_key}] CNY from dedicated page: {[p for p in cny_missing if bank["cny"][p].get("rate")]}')
                    else:
                        # Generic CNY parse
                        cny_generic = _generic_cny_parse(cny_text, cny_tables)
                        if cny_generic:
                            applied = []
                            for pk in cny_missing:
                                if pk in cny_generic and cny_generic[pk].get('rate'):
                                    bank['cny'][pk] = {
                                        'rate': cny_generic[pk]['rate'],
                                        'min_deposit': cny_generic[pk].get('min_deposit'),
                                        'note': cny_generic[pk].get('note', f'從{bank_name}官網提取'),
                                        'source': 'bank',
                                        'fund_type': cny_generic[pk].get('fund_type', 'new_funds'),
                                        'conditions': cny_generic[pk].get('conditions', []),
                                    }
                                    applied.append(pk)
                            if applied:
                                logger.info(f'  [{parser_key}] CNY generic from CNY page: {applied}')
                else:
                    logger.warning(f'  [{parser_key}] Failed to scrape CNY page')

        # ---- Phase 4: HKET override — HKET 為準，覆蓋官網不一致的利率 ----
        hket_overridden = []
        if parser_key in HKET_ARTICLES:
            hket_result, hket_ok = _hket_get_rates(parser_key, bank_name)
            if hket_ok and hket_result:
                # 檢查 HKET 同官網有冇差異，記錄被覆蓋嘅項目
                for cur in ALL_CURRENCIES:
                    if cur not in hket_result:
                        continue
                    for period in ALL_PERIODS:
                        if period not in hket_result.get(cur, {}):
                            continue
                        val = hket_result[cur][period]
                        if not isinstance(val, dict) or val.get('rate') is None:
                            continue
                        existing = bank.get(cur, {}).get(period, {})
                        if isinstance(existing, dict) and existing.get('rate') is not None:
                            if existing.get('rate') != val.get('rate'):
                                hket_overridden.append(f'{cur}/{period}({existing["rate"]}->{val["rate"]})')
                # 直接覆蓋（唔再用 only_missing 模式）
                _apply_result_rates(bank, hket_result, bank_name, source='hket')
                if hket_overridden:
                    logger.info(f"  [{parser_key}] 🔗 HKET overridden {bank_name}: {hket_overridden}")
                    if not bank_updated:
                        verified_updated.append((bank_name, len(hket_overridden)))

    # ---- Metadata ----
    data['last_updated'] = datetime.now(HKT).isoformat()
    data['source'] = '各銀行官網 / HKET香港經濟日報（補充）'

    # Fund type defaults (when not detected from HKET)
    NF_DEFAULTS = {
        '滙豐銀行': 'new_funds', '中銀香港': 'new_funds', '恒生銀行': 'new_funds',
        '渣打銀行': 'new_funds', '工銀亞洲': 'existing_funds', '東亞銀行': 'existing_funds',
        '中信銀行（國際）': 'new_funds', '星展銀行': 'new_funds', '交通銀行': 'new_funds',
        '上海商業銀行': 'existing_funds', '大眾銀行': 'existing_funds', '招商永隆': 'existing_funds',
        '創興銀行': 'existing_funds', '富融銀行': 'existing_funds', '象象銀行': 'existing_funds',
        '眾安銀行': 'existing_funds', '平安數字銀行': 'new_funds', '匯立銀行': 'existing_funds',
        '理慧銀行': 'existing_funds', '螞蟻銀行': 'existing_funds', '集友銀行': 'new_funds',
        '南洋商業銀行': 'new_funds',
    }
    for bank in data['banks']:
        nf = NF_DEFAULTS.get(bank['name'])
        for cur in ALL_CURRENCIES:
            if cur not in bank:
                continue
            for period in ALL_PERIODS:
                entry = bank[cur].get(period)
                if not isinstance(entry, dict):
                    continue
                if entry.get('rate') is not None and entry.get('fund_type') is None and nf:
                    entry['fund_type'] = nf
                if 'conditions' not in entry:
                    entry['conditions'] = []

    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("=" * 50)
    logger.info(f"Update complete:")
    logger.info(f"  ✅ Verified (same): {len(verified_same)}")
    logger.info(f"  🔄 Verified (updated): {len(verified_updated)}")
    logger.info(f"  ❌ Unverified: {len(unverified)}")
    if verified_updated:
        for name, cnt in verified_updated:
            logger.info(f"    Updated: {name} ({cnt} rates changed)")
    if needs_extraction:
        logger.info(f"  Pending extraction: {', '.join(needs_extraction)}")
    if failed_banks:
        logger.info(f"  Failed to scrape: {', '.join(failed_banks)}")
    logger.info(f"Last updated: {data['last_updated']}")
    logger.info("=" * 50)

    # Auto commit and push changes
    try:
        today = datetime.now(HKT).strftime('%Y-%m-%d')
        subprocess.run(['git', 'add', 'data/rates.json', 'data/update.log'], cwd=REPO_ROOT, check=True)
        subprocess.run(['git', 'commit', '-m', f'Auto: deposit rates {today}'], cwd=REPO_ROOT, check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'master'], cwd=REPO_ROOT, check=True)
        subprocess.run(['git', 'push', 'origin', 'master'], cwd=REPO_ROOT, check=True)
        logger.info("✅ Git commit and push completed")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git auto-commit failed: {e}")

    all_verified = len(unverified) == 0
    _send_telegram_summary(verified_same, verified_updated, unverified, needs_extraction, failed_banks, all_verified)
    return all_verified


def _wrap_parser_result(result, bank_name):
    """Wrap a parser result (old format) into the new structured format."""
    wrapped = {'note': result.get('note', f'從{bank_name}官網提取')}
    for cur in ALL_CURRENCIES:
        if cur not in result:
            continue
        wrapped[cur] = {}
        curr_note = result.get(f'{cur}_note', wrapped['note'])
        for period in ALL_PERIODS:
            if period not in result[cur]:
                continue
            val = result[cur][period]
            if isinstance(val, dict):
                wrapped[cur][period] = {
                    'rate': val.get('rate'),
                    'min_deposit': val.get('min_deposit'),
                    'fund_type': val.get('fund_type') or val.get('new_funds') and 'new_funds',
                    'conditions': val.get('conditions', []),
                    'note': curr_note,
                }
            else:
                wrapped[cur][period] = {
                    'rate': val,
                    'fund_type': None,
                    'conditions': [],
                    'note': curr_note,
                }
    return wrapped


def _compare_rates(bank, result):
    """Compare parsed rates against existing bank data.
    Returns set of (currency, period) tuples where rates differ.
    """
    changed = set()
    for cur in ALL_CURRENCIES:
        if cur not in result:
            continue
        for period in ALL_PERIODS:
            if period not in result.get(cur, {}):
                continue
            val = result[cur][period]
            new_rate = val.get('rate') if isinstance(val, dict) else val
            if new_rate is None:
                continue
            existing = bank.get(cur, {}).get(period, {})
            if isinstance(existing, dict):
                old_rate = existing.get('rate')
            else:
                old_rate = existing
            if old_rate is None or abs(float(new_rate) - float(old_rate)) > 0.001:
                changed.add((cur, period))
    return changed


def _apply_result_rates(bank, result, bank_name, source='bank'):
    """Apply parsed rates to bank data structure.
    If only_missing=True, only fill in periods where rate is currently None (supplement mode).
    """
    note = result.get('note', f'從{bank_name}官網提取')
    only_missing = result.get('_only_missing', False)
    supplemented = []
    for cur in ALL_CURRENCIES:
        if cur not in result:
            continue
        curr_note = result.get(f'{cur}_note', note)
        for period in ALL_PERIODS:
            if period not in result.get(cur, {}):
                continue
            val = result[cur][period]
            if not isinstance(val, dict):
                continue
            rate = val.get('rate')
            if rate is None:
                continue

            # In supplement mode, skip if bank already has a rate for this period
            if only_missing:
                existing = bank.get(cur, {}).get(period, {})
                if isinstance(existing, dict) and existing.get('rate') is not None:
                    continue
                supplemented.append(f'{cur}/{period}')

            bank[cur][period] = {
                'rate': rate,
                'min_deposit': val.get('min_deposit') or bank.get(cur, {}).get(period, {}).get('min_deposit'),
                'note': val.get('note') or curr_note,
                'source': source,
                'fund_type': val.get('fund_type'),
                'conditions': val.get('conditions', []),
            }
    return supplemented


def _send_telegram_summary(verified_same, verified_updated, unverified, needs_extraction, failed_banks, all_verified):
    try:
        now = datetime.now(HKT).strftime('%Y-%m-%d %H:%M')
        msg = f"🦆 食息鴨利率更新 ({now})\n"

        if all_verified:
            msg += f"✅ 全部 {len(verified_same) + len(verified_updated)} 間銀行驗證成功\n"
        else:
            msg += f"⚠️ {len(unverified)} 間銀行未能驗證\n"

        msg += f"\n📊 統計：\n"
        msg += f"  ✓ 利率不變: {len(verified_same)}\n"
        msg += f"  🔄 已更新: {len(verified_updated)}\n"
        msg += f"  ❌ 未驗證: {len(unverified)}\n"

        if verified_updated:
            msg += f"\n🔄 已更新利率：\n"
            for name, cnt in verified_updated:
                msg += f"  • {name} ({cnt}項變更)\n"

        if needs_extraction:
            msg += f"\n⏳ 需要手動提取 ({len(needs_extraction)}):\n"
            for name in needs_extraction:
                msg += f"  • {name}\n"

        if failed_banks:
            msg += f"\n❌ 抓取失敗 ({len(failed_banks)}):\n"
            for name in failed_banks:
                msg += f"  • {name}\n"

        if all_verified and not verified_updated:
            msg += "\n✨ 所有利率已驗證，無需更新！"
        elif all_verified:
            msg += "\n✨ 所有銀行已驗證完成！"

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
        update_rates()  # Always returns True when rates.json is written successfully
        return 0        # Return 0 regardless of unverified banks
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
