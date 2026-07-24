"""眾安銀行 ZA Bank - Parser for time deposit rates.

Page: https://bank.za.group/

ZA Bank is a virtual bank. Rates are usually displayed on the main page
or in a savings/deposit section.
"""
import re


def parse(text, tables=None, html=None):
    if not text:
        return None

    hkd = {}
    usd = {}

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
                if rate > 0:
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
                    if rate > 0:
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
                    if rate > 0:
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