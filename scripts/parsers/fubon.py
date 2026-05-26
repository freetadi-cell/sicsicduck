"""富邦銀行 Fubon Bank - Parser for time deposit rates."""
import re

def parse(text, tables=None):
    """Parse Fubon Bank time deposit rates.
    
    Page has two sections:
    1. 新資金定期存款優惠: 港元 2.8% (3m), 美元 3.9% (3m)
    2. Fubon+ 手機限定: multiple tiers and periods

    Prioritize new fund rates (better rates, no app requirement).
    """
    if not text:
        return None
    
    rates = {}
    
    # First try new fund section (better rates, no app requirement)
    nf_idx = text.find('新資金定期存款優惠')
    if nf_idx >= 0:
        nf_section = text[nf_idx:]
        
        # Find the rate table after "分行/Fubon+手機應用程式"
        # Structure: 港元 <whitespace> 2.8% ... 美元 <whitespace> 3.9%
        # Skip the header line: 港元 500,000 (has numbers before %)
        hkd_m = re.search(r'港元\s+(\d+\.\d+)%', nf_section)
        usd_m = re.search(r'美元\s+(\d+\.\d+)%', nf_section)
        
        if hkd_m:
            rates['hkd'] = {'3m': float(hkd_m.group(1))}
        if usd_m:
            rates['usd'] = {'3m': float(usd_m.group(1))}
        
        if rates:
            rates['note'] = '新資金定期存款優惠'
            return rates
    
    # Fallback: Fubon+ 手機限定
    fubon_idx = text.find('Fubon+ 手機應用程式限定')
    if fubon_idx >= 0:
        fubon_section = text[fubon_idx:fubon_idx+3000]
        
        # Find the highest amount tier (500,000或以上)
        # Rates are in a table: period × amount
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            # Look for rate near the period label
            idx = fubon_section.find(label)
            if idx >= 0:
                nearby = fubon_section[idx:idx+200]
                pcts = re.findall(r'(\d+\.\d+)%', nearby)
                if pcts:
                    hkd_rates[period] = max(float(x) for x in pcts)
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
            rates['note'] = 'Fubon+手機應用程式定存利率'
    
    if rates:
        return rates
    return None