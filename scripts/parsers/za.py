"""眾安銀行 ZA Bank - Parser for time deposit rates.

Page: https://bank.za.group/hk/deposit

ZA Bank is a virtual bank. Rates are usually very low (0.1% for most periods).

⚠️ Bug fix (2026-07-25):
- 舊版會將 0.1% 嘅利率錯誤提取，尤其係 USD 1m existing_funds 出現 10.0%
- 新版加強利率合理性檢查，過濾超出合理範圍嘅值
- ZA Bank 嘅定期存款利率通常極低（0.1%），唔會超過 1%
"""
import re


def parse(text, tables=None, html=None):
    """Parse ZA Bank time deposit rates.
    
    ZA Bank rates are typically very low (0.1% for most periods).
    Any rate > 1% for ZA Bank is likely a parsing error.
    """
    if not text:
        return None

    hkd = {}
    usd = {}

    # ZA Bank 定期存款利率合理上限（2026年）
    # ZA Bank 利率極低，通常 0.1%，唔會超過 1%
    ZA_RATE_MAX = 1.0

    # Look for time deposit rates
    td_idx = text.find('定期存款')
    if td_idx < 0:
        td_idx = text.find('定期')
    
    if td_idx >= 0:
        section = text[td_idx:td_idx + 3000]
        for period, label in [('1m', r'1\s*個?月'), ('2m', r'2\s*個?月'),
                               ('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'),
                               ('12m', r'12\s*個?月')]:
            m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
            if m:
                rate = float(m.group(1))
                # Filter out unreasonable rates for ZA Bank
                if 0 < rate <= ZA_RATE_MAX:
                    hkd[period] = {
                        'rate': rate,
                        'min_deposit': 1,
                        'note': '眾安銀行定期存款',
                        'source': 'bank'
                    }

    # Try looking for HKD/USD specific sections
    for currency, store in [('hkd', hkd), ('usd', usd)]:
        curr_label = '港元' if currency == 'hkd' else '美元'
        curr_idx = text.find(curr_label)
        if curr_idx >= 0:
            section = text[curr_idx:curr_idx + 2000]
            for period, label in [('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'), ('12m', r'12?\s*個?月')]:
                m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
                if m:
                    rate = float(m.group(1))
                    if 0 < rate <= ZA_RATE_MAX:
                        store[period] = {
                            'rate': rate,
                            'min_deposit': 1,
                            'note': '眾安銀行定期存款',
                            'source': 'bank'
                        }

    # Try tables
    if tables and not hkd:
        for table in tables:
            table_str = str(table)
            for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
                m = re.search(rf'{label}\s*個?月\s*[^%]*?(\d+\.?\d*)%', table_str)
                if m:
                    rate = float(m.group(1))
                    if 0 < rate <= ZA_RATE_MAX:
                        hkd[period] = {
                            'rate': rate,
                            'min_deposit': 1,
                            'note': '眾安銀行定期存款',
                            'source': 'bank'
                        }

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd

    if result:
        return result
    return None
