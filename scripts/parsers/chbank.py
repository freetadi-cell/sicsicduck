"""創興銀行 Chong Hing Bank - Parser for 雲利率 (e-rate / cloud rates).

Page: https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml

注意：網頁用 inner_text() 數字會黏連，所以用 HTML cell（<td>/<th>）逐 cell 讀。

雲利率 table 結構（HTML cells，每 row 係 list of cell text）：
Row0: ['貨幣', '金額', '存款期']
Row1: ['1天','7天','14天','1個月','2個月','3個月','6個月','9個月','12個月','24個月']  ← 標題行(10 cells)
Row2: ['港 元','5,000 至 49,999','0.0010',...]  ← 貨幣行：12 cells（貨幣+金額+10利率）
Row3: ['50,000 至 499,999','0.0010',...]        ← 金額行：11 cells（金額+10利率）
...
Row6: ['美 元','1,000 至 9,999',...]
Row9: ['人民幣','5,000 至 49,999',...]

關鍵索引：
- 標題行：col_idx['3個月']=5, '6個月'=6, '12個月'=8（10 cells，0-based）
- 數據行：貨幣行(12 cells) 利率由 idx2 開始；金額行(11 cells) 利率由 idx1 開始
  所以 row_idx = header_idx + offset，offset = len(row) - 10（靈活計）

注意 pipeline 傳入嘅 tables 可能係「string body text + dict tables」混合 list，
所以 _find_and_parse 分兩輪：先掃 dict format（HTML cells 可靠），
string format（inner_text 黏連唔可靠）只作後備。
"""
import logging

logger = logging.getLogger(__name__)

CURRENCY_LABELS = {'港 元': 'hkd', '美 元': 'usd', '人民幣': 'cny'}
# 支援全部年期：1個月/2個月/3個月/6個月/9個月/12個月（24個月唔入網站顯示）
PERIOD_MAP = {
    '1個月': '1m', '2個月': '2m', '3個月': '3m',
    '6個月': '6m', '9個月': '9m', '12個月': '12m',
}
ALL_PERIODS = ['1天', '7天', '14天', '1個月', '2個月', '3個月', '6個月', '9個月', '12個月', '24個月']

# 標題行有幾多個利率欄（= 10）
HEADER_RATE_CELLS = 10


def parse(text=None, tables=None, html=None):
    if not tables:
        return None
    cloud = _find_and_parse(tables, '雲利率')
    if cloud:
        return cloud
    return _find_and_parse(tables, '牌價')


def _find_and_parse(tables, keyword):
    """喺 tables 揾包含 keyword 嘅 table 並 parse.

    分兩輪：
    - 第一輪：dict format（HTML cells，caption / cells 命中 keyword）
    - 第二輪（後備）：string format（body text / inner_text，黏連唔可靠）
    咁樣即使 body text(string) 排喺 dict tables 前面，都唔會俾 fallback 搶走。
    """
    # 第一輪：dict format 優先
    for table in tables:
        if not isinstance(table, dict):
            continue
        cells = table.get('cells')
        caption = str(table.get('caption', ''))
        if caption and keyword in caption:
            parsed = _parse_cells(cells if cells else [], keyword)
            if parsed:
                return parsed
        if cells and any(keyword in str(c) for row in cells for c in row):
            parsed = _parse_cells(cells, keyword)
            if parsed:
                return parsed

    # 第二輪：string format 後備
    for table in tables:
        if isinstance(table, dict):
            continue
        if keyword in str(table):
            parsed = _parse_text(str(table))
            if parsed:
                return parsed
    return None


def _parse_cells(cells, keyword):
    """從 HTML cells parse. Returns {hkd:{'3m':{...}},...}，每期限取最高檔。"""
    # 1. 定位標題行 → col_idx（標題 text → 喺標題行嘅 index）
    col_idx = {}
    for row in cells:
        flat = [str(c).strip() for c in row]
        if any(c == '3個月' for c in flat) and any(c == '1天' for c in flat):
            for i, c in enumerate(flat):
                if c in ALL_PERIODS:
                    col_idx[c] = i
            break
    if not col_idx:
        return None

    # 2. 掃行，按貨幣分組
    per_currency = {}  # cur -> {period: rate}
    cur_key = None

    for row in cells:
        flat = [str(c).strip() for c in row]
        if not flat or not any(flat):
            continue

        # 貨幣標籤行
        if flat[0] in CURRENCY_LABELS:
            cur_key = CURRENCY_LABELS[flat[0]]
            _extract_row(flat, col_idx, cur_key, per_currency)
            continue

        # 非貨幣行
        if cur_key is None:
            continue
        if any(c in ('貨幣', '金額', '存款期') for c in flat):
            continue
        if any(c == '1天' for c in flat):
            continue
        _extract_row(flat, col_idx, cur_key, per_currency)

    # 3. 組最終輸出（保留每個 period 所屬金額檔嘅 min_deposit）
    out = {}
    for cur, pr in per_currency.items():
        if not pr:
            continue
        out[cur] = {
            period: {
                'rate': info['rate'],
                'min_deposit': info['min_deposit'],
                'note': '雲利率（網上/流動理財）' if '雲' in keyword else '牌價利率',
                'source': 'bank',
            }
            for period, info in pr.items()
        }
    return out if out else None


def _extract_row(flat, col_idx, cur_key, per_currency):
    """從單一數據行抽所有年期，存入 per_currency[cur_key]（取最高，並記返 min_deposit）。"""
    # offset = 數據行有幾多個「前置欄」（貨幣/金額）＝ len(row) - 標題行利率欄數
    offset = len(flat) - HEADER_RATE_CELLS
    if offset < 0:
        offset = 0

    # 記錄呢行嘅最低存款額（金額檔，通常喺第一欄，形如 '5,000 至 49,999' / '50,000,001 或以上'）
    min_deposit = _parse_min_deposit(flat)

    if cur_key not in per_currency:
        per_currency[cur_key] = {}  # period -> {'rate': float, 'min_deposit': float}
    for label, period_key in PERIOD_MAP.items():
        header_idx = col_idx.get(label)
        if header_idx is None:
            continue
        row_idx = header_idx + offset
        if row_idx >= len(flat):
            continue
        val = flat[row_idx]
        if val in ('-------', '—', '-', ''):
            continue
        try:
            rate = float(val)
        except ValueError:
            continue
        if 0 < rate < 100:
            cur = per_currency[cur_key].get(period_key)
            if cur is None or rate > cur['rate']:
                per_currency[cur_key][period_key] = {'rate': rate, 'min_deposit': min_deposit}


def _parse_min_deposit(flat):
    """從數據行嘅金額欄（通常第一欄）抽最低存款額。

    支援格式：
    - '5,000 至 49,999'      → 5000
    - '50,000,001 或以上'    → 50000001
    - '1,000 至 9,999'       → 1000
    攞唔到就預設 5000。
    """
    import re
    for c in flat:
        m = re.match(r'^[\d,]+', c.replace(' ', ''))
        if m:
            try:
                return float(m.group(0).replace(',', ''))
            except ValueError:
                pass
    return 5000


def _parse_text(table_str):
    """string format 後備：inner_text()/body text（數字黏連），唔可靠但防 crash。"""
    import re
    out = {}
    for label, cur in CURRENCY_LABELS.items():
        idx = table_str.find(label)
        if idx < 0:
            continue
        nums = [float(n) for n in re.findall(r'\d+\.\d{4}', table_str[idx:idx + 2000]) if 0 < float(n) < 100]
        if len(nums) > 8:
            out[cur] = {
                period: {'rate': nums[col], 'min_deposit': 5000,
                         'note': '雲利率（網上/流動理財）', 'source': 'bank'}
                for period, col in {'3m': 5, '6m': 6, '12m': 8}.items() if col < len(nums)
            }
    return out if out else None
