"""匯立銀行 WeLab Bank - Parser for GoSave 2.0 time deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse WeLab Bank GoSave 2.0 rates.
    
    Page shows currency tabs: HKD, USD, CNY, AUD, GBP
    Default visible tab is HKD.
    Format: 3個月\t2.85%⁵  (Chinese format with tab separator)
    """
    if not text:
        return None
    
    rates = {}
    note = 'GoSave 2.0 定期存款'
    
    # HKD rates - look for Chinese format: 3個月 2.85%
    hkd_rates = {}
    for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Pattern: 3個月\t2.85%⁵ or 3個月 2.85%
        pattern = rf'{label}[\s\t]+(\d+\.\d+)%'
        m = re.search(pattern, text)
        if m:
            hkd_rates[period] = {
                'rate': float(m.group(1)),
                'min_deposit': 1,
                'note': note,
                'source': 'bank'
            }
    
    # Fallback: try English format
    if not hkd_rates:
        for period, label in [('1m', '1-month'), ('3m', '3-month'), ('6m', '6-month'), ('12m', '12-month')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, text)
            if m:
                hkd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 1,
                    'note': note,
                    'source': 'bank'
                }
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    if rates:
        return rates
    return None