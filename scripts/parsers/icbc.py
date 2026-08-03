"""工銀亞洲 ICBC Asia - Parser (自動合併兩頁利率).

資料來源（自動，不寫死任何利率）：
1. 新資金定期存款推廣 (new-funds-time-deposit.html) — 分行 98/188/388 天
   URL: https://www.icbcasia.com/hk/tc/personal/latest-promotion/new-funds-time-deposit.html
2. 網上定期存款優惠 (online-time-deposit.html) — 網上 1/2/3/6/12 個月
   URL: https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html

合併邏輯：
- 先從「新資金推廣」頁抽取（98天→3m, 188天→6m, 388天→12m）
- 再從「網上定存」頁補充其他年期（1m, 2m, 以及新資金缺嘅年期）
- 同一 key 若兩頁都有：以新資金推廣頁為準（主優惠優先）

Parser 接收格式：
- text / tables = 兩頁嘅 list，每頁由分隔符分開：
  tables 參數可以係 [頁1內容, 頁2內容, ...]
  （update_rates.py 會把多個 URL 抓到嘅頁面全部塞入 tables）
"""
import re

CURRENCY_MAP = {
    '港幣': 'hkd', '港币': 'hkd',
    '美元': 'usd',
    '人民幣': 'cny', '人民币': 'cny',
}

# 新資金推廣頁: 98/188/388 天 -> 3m/6m/12m
NEW_FUND_TENOR_MAP = {
    '98天': '3m',
    '188天': '6m',
    '388天': '12m',
}
# 網上定存頁: 1/2/3/6/12 個月 -> 1m/2m/3m/6m/12m
ONLINE_TENOR_MAP = {
    '1個月': '1m', '1个月': '1m',
    '2個月': '2m', '2个月': '2m',
    '3個月': '3m', '3个月': '3m',
    '6個月': '6m', '6个月': '6m',
    '12個月': '12m', '12个月': '12m',
}

MIN_DEPOSITS = {'hkd': 50000, 'usd': 15000, 'cny': 50000}


def parse(text, tables=None, html=None):
    """Parse ICBC rates by auto-combining 新資金推廣 + 網上定存 pages.

    接受多頁：tables 可包含多頁文本，或 text 用分隔符分開多頁。
    """
    # 收集所有可用頁面文本
    pages = []
    if tables:
        for t in tables:
            if isinstance(t, str) and t.strip():
                pages.append(t)
    if html and isinstance(html, str) and html.strip():
        pages.append(html)
    if text and isinstance(text, str) and text.strip():
        pages.append(text)

    if not pages:
        return None

    # 分離「新資金」頁與「網上定存」頁
    new_fund_pages = [p for p in pages if '新資金' in p or '全新資金' in p or '98天' in p]
    online_pages = [p for p in pages if '網上' in p and '1個月' in p]

    rates = {}

    # 1) 優先：新資金推廣頁
    new_fund_rates = {}
    for page in new_fund_pages:
        new_fund_rates.update(_parse_new_fund_page(page))
    rates.update(new_fund_rates)

    # 2) 補充：網上定存頁（唔覆蓋新資金已有嘅 key）
    online_rates = {}
    for page in online_pages:
        online_rates.update(_parse_online_page(page))
    for cur, tmap in online_rates.items():
        rates.setdefault(cur, {})
        for ten, rate_info in tmap.items():
            # 新資金優先：網上頁只補缺
            if ten not in rates[cur]:
                rates[cur][ten] = rate_info

    if not any(rates.get(c) for c in ('hkd', 'usd', 'cny')):
        return None
    return rates


def _parse_new_fund_page(text):
    """解析新資金定期存款推廣頁（分行 98/188/388 天），零售銀行個人客戶檔。"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    rates = {}  # currency -> {tenor: rate_info}

    for line in lines:
        # 貨幣判斷
        cur = None
        for cname, ckey in CURRENCY_MAP.items():
            if cname in line:
                cur = ckey
                break
        if not cur:
            continue

        # 只取零售檔（最低門檻）
        if '工銀財富' in line or '理財金客戶' in line or '理財金' in line:
            continue
        if '（只適用於' in line:
            continue
        # 零售檔行: "港幣50,000元或以上  2.85%  2.85%  2.85%"
        if '50,000元或以上' not in line and '15,000元或以上' not in line:
            continue

        # 提取 98/188/388 天利率
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) >= 3:
            tenor_keys = ['3m', '6m', '12m']  # 98/188/388
            rates.setdefault(cur, {})
            for i, ten in enumerate(tenor_keys[:len(pcts)]):
                rates[cur][ten] = {
                    'rate': float(pcts[i]),
                    'min_deposit': MIN_DEPOSITS.get(cur, 50000),
                    'note': '工銀亞洲新資金定期存款推廣（分行）',
                    'source': 'bank'
                }

    return rates


def _parse_online_page(text):
    """解析網上定期存款優惠頁（網上 1/2/3/6/12 個月），零售最低檔。"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    rates = {}

    for line in lines:
        cur = None
        for cname, ckey in CURRENCY_MAP.items():
            if cname in line:
                cur = ckey
                break
        if not cur:
            continue

        # 跳過表頭 / 高門檻檔 / 財富客戶
        if '貨幣' in line or '定期存款' in line and '％' not in line and '%' not in line:
            continue
        if '（只適用於' in line or '工銀財富' in line:
            continue
        # 高門檻檔:「800,000或以上」「100,000或以上」「500,000或以上」
        if '或以上' in line and '以下' not in line:
            continue
        # 零售檔行需含「至...以下」 或 「50,000...」
        if '以下' not in line:
            continue

        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) >= 5:
            tenor_keys = ['1m', '2m', '3m', '6m', '12m']
            rates.setdefault(cur, {})
            for i, ten in enumerate(tenor_keys):
                rates[cur][ten] = {
                    'rate': float(pcts[i]),
                    'min_deposit': MIN_DEPOSITS.get(cur, 50000),
                    'note': '工銀亞洲網上定期存款優惠',
                    'source': 'bank'
                }

    return rates