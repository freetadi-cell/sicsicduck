"""平安數字銀行 PAO Bank - Parser for time deposit rates."""
import re

def parse(text, tables=None):
    """Parse PAO Bank (平安數字銀行) time deposit rates.
    
    Page format:
    定期存款年利率
    存款期  港元 (年利率)  人民幣 (年利率)  美元 (年利率)
    1個月  2.40%  0.10%  2.80%
    3個月  2.90%  0.30%  2.70%
    6個月  2.70%  0.40%  2.70%
    12個月  2.60%  0.50%  3.80%
    """
    if not text:
        return None
    
    rates = {}
    note = '定期存款年利率'
    
    # Find time deposit section
    td_idx = text.find('定期存款年利率')
    if td_idx < 0:
        return None
    
    section = text[td_idx:td_idx+800]
    
    # Parse each period row
    hkd_rates = {}
    usd_rates = {}
    
    for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Pattern: 3個月  2.90%  0.30%  2.70%
        m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\d+\.\d+%\s+(\d+\.\d+)%', section)
        if m:
            hkd_rates[period] = float(m.group(1))
            usd_rates[period] = float(m.group(2))
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    if usd_rates:
        rates['usd'] = usd_rates
    
    if rates:
        rates['note'] = note
        return rates
    return None
