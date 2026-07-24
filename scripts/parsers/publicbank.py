"""大眾銀行 Public Bank - Parser for deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse Public Bank HK deposit rates (HKD, USD, CNY).
    
    Page has clear table:
    一個月  2.0000%  2.0500%  2.1000%
    三個月  2.4000%  2.4500%  2.5000%
    
    Take the highest tier (>= $500,000).
    """
    if not text:
        return None
    
    rates = {}
    note = '定期存款年利率'
    
    # HKD section - look for rates after "港元定期存款年利率"
    hkd_idx = text.find('港元定期存款年利率')
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx+2000]
        
        hkd_rates = {}
        # Web fetch markdown format: 一個月 2.2000% (single rate per line)
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            # Try markdown format first: "一個月2.2000%"
            m = re.search(rf'{label}\s*(\d+\.\d+)%', hkd_section)
            if m:
                hkd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 10000,
                    'note': note,
                    'source': 'bank'
                }
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # USD section - look for rates after "外幣定期存款年利率" or "美元"
    usd_idx = text.find('外幣定期存款年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+2000]
        
        usd_rates = {}
        # Web fetch markdown format: 一個月 3.4500%
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            m = re.search(rf'{label}\s*(\d+\.\d+)%', usd_section)
            if m:
                usd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 2000,
                    'note': note,
                    'source': 'bank'
                }
        
        if usd_rates:
            rates['usd'] = usd_rates
    
    # CNY section - look for "人民幣" after USD section
    cny_idx = text.find('人民幣', usd_idx if usd_idx >= 0 else 0)
    if cny_idx >= 0:
        cny_section = text[cny_idx:cny_idx+1000]
        
        cny_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            m = re.search(rf'{label}\s*(\d+\.\d+)%', cny_section)
            if m:
                cny_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 10000,
                    'note': note,
                    'source': 'bank'
                }
        
        if cny_rates:
            rates['cny'] = cny_rates
    
    if rates:
        return rates
    return None