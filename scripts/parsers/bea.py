"""東亞銀行 BEA - Parser for time deposit rates."""
import re

def parse(text, tables=None):
    """Parse BEA time deposit rates from promo page.
    
    Page format:
    $100,000 - $10,000,000
    3個月  2.60%  3.50%
    6個月  2.60%  3.60%
    12個月  2.55%  3.60%
    """
    if not text:
        return None
    
    rates = {}
    note = '顯卓理財特惠定期存款利率'
    
    # Find the rate table section
    # Look for pattern: 存款期 followed by rates
    hkd_rates = {}
    usd_rates = {}
    
    for period, label in [('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Pattern: 3個月  2.60%  3.50%
        m = re.search(rf'{label}\s+(\d+\.\d+)%\s+(\d+\.\d+)%', text)
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
