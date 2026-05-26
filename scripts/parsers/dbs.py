"""星展銀行 DBS - Parser for online time deposit rates."""
import re

def parse(text, tables=None):
    """Parse DBS HK online time deposit rates.
    
    Page shows online offers. The actual rates are shown in a dynamic table
    that may not fully render. But the promo text shows key rates.
    """
    if not text:
        return None
    
    rates = {}
    note = '網上定期存款特惠利率'
    
    # Look for HKD rates in the promotion text
    # "enjoy up to HKD 2.50% p.a. and USD 3.90% p.a."
    hkd_promo = re.search(r'HKD\s+(\d+\.\d+)%\s*p\.a\.', text)
    usd_promo = re.search(r'USD\s+(\d+\.\d+)%\s*p\.a\.', text)
    
    if hkd_promo:
        rates['hkd'] = {'3m': float(hkd_promo.group(1))}
    
    if usd_promo:
        rates['usd'] = {'3m': float(usd_promo.group(1))}
    
    # Also look for board rate table if available
    # The actual rates are loaded dynamically, so we may not get them
    
    if rates:
        rates['note'] = note
        return rates
    return None
