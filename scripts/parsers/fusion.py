"""富融銀行 Fusion Bank - Parser for time deposit rates.

Page: https://www.fusionbank.com/

Note: Site may block automated access (Tencent Cloud EdgeOne).
When accessible, extract rates from the deposit section.
"""
import re


def parse(text, tables=None, html=None):
    if not text:
        return None

    # Check if blocked
    if 'Restricted Access' in text or 'blocked you' in text:
        return None

    hkd = {}
    usd = {}

    # Look for 定期存款 section
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
                    hkd[period] = rate

    # Look for HKD/USD sections
    for currency, store in [('hkd', hkd), ('usd', usd)]:
        curr_label = '港元' if currency == 'hkd' else '美元'
        idx = text.find(curr_label)
        if idx >= 0:
            section = text[idx:idx + 2000]
            for period, plabel in [('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'), ('12m', r'12?\s*個?月')]:
                m = re.search(rf'{plabel}\s*[^%]*?(\d+\.?\d*)%', section)
                if m:
                    rate = float(m.group(1))
                    if rate > 0:
                        store[period] = rate

    # Try tables
    if tables:
        for table in tables:
            table_str = str(table)
            if '定期' in table_str or '%' in table_str:
                for period, label in [('3m', '3'), ('6m', '6'), ('12m', '12')]:
                    m = re.search(rf'{label}\s*個?月\s*[^%]*?(\d+\.?\d*)%', table_str)
                    if m:
                        rate = float(m.group(1))
                        if rate > 0:
                            hkd[period] = rate

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd

    if result:
        result['note'] = '從富融銀行官網提取'
        return result
    return None
