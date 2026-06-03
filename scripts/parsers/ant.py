"""螞蟻銀行 Ant Bank - Parser for time deposit rates.

Page: https://www.antbank.hk/

Ant Bank is a virtual bank. The main page shows:
- 活期利率 (savings rate): 餘額+ 日賺 高達 X 厘
- 定期存款 rates may be in a separate section

We try to extract whatever rate info is available from the page.
"""
import re


def parse(text, tables=None, html=None):
    if not text:
        return None

    hkd = {}
    usd = {}

    # Look for 定期存款 section
    td_idx = text.find('定期存款')
    if td_idx >= 0:
        section = text[td_idx:td_idx + 3000]
        
        # Try to find rate patterns in the 定期存款 section
        # Common patterns: 1個月 X.XX%, 3個月 X.XX%, etc.
        for period, label in [('1m', r'1\s*个?月'), ('2m', r'2\s*个?月'),
                               ('3m', r'3\s*个?月'), ('6m', r'6\s*个?月'),
                               ('12m', r'12\s*个?月')]:
            m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
            if m:
                rate = float(m.group(1))
                if rate > 0:
                    hkd[period] = rate

    # Look for savings / 活期 rate as fallback
    if not hkd:
        savings_match = re.search(r'(?:高達|年利率|利率)[^0-9]*(\d+\.?\d*)\s*(?:厘|%|%)', text)
        if savings_match:
            rate = float(savings_match.group(1))
            if rate > 0:
                # This is a savings rate, not time deposit - return None
                # unless we can find specific time deposit rates
                pass

    # Try tables if available
    if tables and not hkd:
        for table in tables:
            table_str = str(table)
            if '定期' in table_str or '存款' in table_str:
                for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
                    m = re.search(rf'{label}\s*个?月\s*[^%]*?(\d+\.?\d*)%', table_str)
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
        result['note'] = '從螞蟻銀行官網提取'
        return result
    return None
