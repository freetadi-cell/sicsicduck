"""東亞銀行 BEA - Parser for online time deposit rates."""
import re

def parse(text, tables=None):
    """Parse BEA online time deposit rates.
    
    Page has:
    網上港元定期存款特惠年利率 (%)
    存款期  顯卓私人理財/顯卓理財  至尊理財  BEA GOAL/其他
    3個月   2.45 / 2.35  2.40 / 2.35  2.40 / 2.35
    
    Take 顯卓理財 new fund rate (first number in first column).
    
    USD similarly.
    """
    if not text:
        return None
    
    rates = {}
    note = '網上定期存款特惠年利率（新資金）'
    
    # HKD section
    hkd_idx = text.find('網上港元定期存款特惠年利率')
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx+800]
        
        hkd_rates = {}
        # Pattern: 3個月  2.45 / 2.35  ...  (take first number = new fund rate)
        for period, label in [('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)\s*/\s*\d+\.\d+'
            m = re.search(pattern, hkd_section)
            if m:
                hkd_rates[period] = float(m.group(1))
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # USD section
    usd_idx = text.find('網上美元定期存款特惠年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+800]
        
        usd_rates = {}
        for period, label in [('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)\s*/\s*\d+\.\d+'
            m = re.search(pattern, usd_section)
            if m:
                usd_rates[period] = float(m.group(1))
        
        if usd_rates:
            rates['usd'] = usd_rates
    
    if rates:
        rates['note'] = note
        return rates
    return None
