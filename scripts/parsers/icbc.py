"""工銀亞洲 ICBC Asia - Parser for online time deposit rates.

Page: https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html

Table format (retail tier, HKD $50k-800k):
貨幣	定期存款金額	1個月	2個月	3個月	6個月	12個月
港幣	50,000至800,000以下	1.50%	2.10%	2.75%	2.65%	2.65%
美元	15,000至100,000以下	3.10%	3.35%	3.60%	3.60%	3.60%
人民幣	50,000至500,000以下	0.75%	1.05%	1.15%	1.15%	1.25%
"""
import re

TENOR_MAP = {
    '1個月': '1m', '1个月': '1m',
    '2個月': '2m', '2个月': '2m',
    '3個月': '3m', '3个月': '3m',
    '6個月': '6m', '6个月': '6m',
    '12個月': '12m', '12个月': '12m',
}

CURRENCY_MAP = {
    '港幣': 'hkd', '港币': 'hkd',
    '美元': 'usd',
    '人民幣': 'cny', '人民币': 'cny',
}


def parse(text, tables=None, html=None):
    """Parse ICBC online time deposit rates from page text."""
    if not text:
        return None

    rates = {}

    # Try table-based parsing first (from playwright / html tables)
    if tables:
        for table in tables:
            table_str = str(table)
            if '1個月' in table_str and '3個月' in table_str:
                parsed = _parse_online_table(table_str)
                if parsed:
                    rates.update(parsed)
                    break

    # Fallback: parse from text
    if not rates and text:
        parsed = _parse_online_text(text)
        if parsed:
            rates.update(parsed)

    if rates:
        return rates
    return None


def _parse_online_table(table_str):
    """Parse the online time deposit rate table (retail tier)."""
    lines = table_str.split('\n')
    rates = {}
    main_rates = {}  # key: currency, value: {tenor: rate}

    for line in lines:
        # Determine currency
        cur = None
        for cname, ckey in CURRENCY_MAP.items():
            if cname in line:
                cur = ckey
                break
        if not cur:
            continue

        # Skip the header row and wealth/>=800k tier rows
        if '港元' in line and '定期存款' in line:
            continue
        if '港元' in line and '年利率' in line:
            continue
        if '貨幣' in line:
            continue
        if '（只適用於' in line or '工銀財富' in line:
            continue
        if '或以上' in line and '以下' not in line:
            # This is the higher tier (>=800k / >=100k / >=500k), skip
            continue

        # Retail tier: "50,000至800,000以下" or "15,000至100,000以下" or "50,000至500,000以下"
        if '至' not in line and '以下' not in line:
            continue

        # Extract rates: 1.50%	2.10%	2.75%	2.65%	2.65%
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) >= 5:
            tenors = ['1m', '2m', '3m', '6m', '12m']
            for i, ten in enumerate(tenors):
                main_rates[cur] = main_rates.get(cur, {})
                main_rates[cur][ten] = float(pcts[i])

    # Convert to rates.json format with min_deposit
    min_deposits = {'hkd': 50000, 'usd': 15000, 'cny': 50000}
    hkd_override = {'3m': 3.0, '6m': 3.0}  # 新資金推廣（98/188天）優惠值
    for cur, tenor_rates in main_rates.items():
        rates[cur] = {}
        for ten, rate in tenor_rates.items():
            is_hkd_override = cur == 'hkd' and ten in hkd_override
            rates[cur][ten] = {
                'rate': hkd_override[ten] if is_hkd_override else rate,
                'min_deposit': min_deposits.get(cur, 50000),
                'note': '工銀亞洲新資金定期存款推廣（98/188天）' if is_hkd_override else '工銀亞洲網上定期存款優惠',
                'source': 'bank'
            }

    return rates


def _parse_online_text(text):
    """Fallback: parse rates from cleaned text."""
    # Find the table section anchored by "貨幣" header
    # Look for the lines with the main table
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    rates = {}
    main_rates = {}

    for i, line in enumerate(lines):
        # Determine currency
        cur = None
        for cname, ckey in CURRENCY_MAP.items():
            if cname in line:
                cur = ckey
                break
        if not cur:
            continue

        # Skip header, wealth tiers
        if '（只適用於' in line or '工銀財富' in line:
            continue
        if '或以上' in line and '以下' not in line:
            continue
        if '至' not in line and '以下' not in line:
            continue
        if '貨幣' in line:
            continue

        # Extract rates: 1.50% 2.10% 2.75% 2.65% 2.65%
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) >= 5:
            tenors = ['1m', '2m', '3m', '6m', '12m']
            for j, ten in enumerate(tenors):
                main_rates[cur] = main_rates.get(cur, {})
                main_rates[cur][ten] = float(pcts[j])

    min_deposits = {'hkd': 50000, 'usd': 15000, 'cny': 50000}
    hkd_override = {'3m': 3.0, '6m': 3.0}  # 新資金推廣（98/188天）優惠值
    for cur, tenor_rates in main_rates.items():
        rates[cur] = {}
        for ten, rate in tenor_rates.items():
            is_hkd_override = cur == 'hkd' and ten in hkd_override
            rates[cur][ten] = {
                'rate': hkd_override[ten] if is_hkd_override else rate,
                'min_deposit': min_deposits.get(cur, 50000),
                'note': '工銀亞洲新資金定期存款推廣（98/188天）' if is_hkd_override else '工銀亞洲網上定期存款優惠',
                'source': 'bank'
            }

    return rates