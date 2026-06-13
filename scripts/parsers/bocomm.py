"""交通銀行 Bank of Communications - Parser for time deposit rates.

Page: https://www.bankcomm.com.hk/hk/shtml/hk/tw/2005155/2005178/2005179/list.shtml

Data includes HKD, USD, and CNY rates (especially short-term exchange rates).
"""
import re


def parse(text, tables=None, html=None):
    if not text:
        return None

    hkd = {}
    usd = {}
    cny = {}

    # Look for 定期存款 section
    td_idx = text.find('定期存款')
    if td_idx < 0:
        td_idx = text.find('定期')
    
    if td_idx >= 0:
        section = text[td_idx:td_idx + 3000]
        
        # Try rate patterns for HKD
        for period, label in [('1m', r'1\s*個?月'), ('2m', r'2\s*個?月'),
                               ('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'),
                               ('12m', r'12\s*個?月')]:
            m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
            if m:
                rate = float(m.group(1))
                if rate > 0:
                    hkd[period] = rate

    # Look for specific rate sections
    for currency, store in [('hkd', hkd), ('usd', usd)]:
        labels = ['港元', '港幣'] if currency == 'hkd' else ['美元', '美金']
        for curr_label in labels:
            idx = text.find(curr_label)
            if idx >= 0:
                section = text[idx:idx + 2000]
                for period, plabel in [('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'), ('12m', r'12\s*個?月')]:
                    m = re.search(rf'{plabel}\s*[^%]*?(\d+\.?\d*)%', section)
                    if m:
                        rate = float(m.group(1))
                        if rate > 0:
                            store[period] = rate

    # CNY section - look for "CNY N天 X.XX%" or "人民幣 N個月 X.XX%"
    cny_idx = text.find('CNY')
    if cny_idx < 0:
        cny_idx = text.find('人民幣')
    
    if cny_idx >= 0:
        cny_section = text[cny_idx:cny_idx + 1500]
        
        # Short-term exchange rates: "CNY 7天 10.00%"
        m = re.search(r'CNY\s*(\d+)\s*天\s*(\d+\.?\d*)%', cny_section)
        if m:
            days = int(m.group(1))
            if days == 7:
                cny['1w'] = float(m.group(2))
        
        # Monthly rates: "人民幣 3個月 X.XX%"
        for period, plabel in [('1m', r'1\s*個?月'), ('3m', r'3\s*個?月'), 
                               ('6m', r'6\s*個?月'), ('12m', r'12\s*個?月')]:
            m = re.search(rf'(?:人民幣|CNY)[^%]*?{plabel}[^%]*?(\d+\.?\d*)%', cny_section)
            if m:
                rate = float(m.group(1))
                if rate > 0:
                    cny[period] = rate

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd
    if cny:
        result['cny'] = cny

    if result:
        result['note'] = '從交通銀行官網提取'
        return result
    return None
