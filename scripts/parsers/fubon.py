"""富邦銀行 Fubon Bank - Parser for time deposit rates."""
import re

def parse(text, tables=None):
    """Parse Fubon Bank time deposit rates.
    
    Page has two sections:
    1. 新資金定期存款: 港元 2.8% (3m), 美元 3.9% (3m)
    2. Fubon+ 手機限定: multiple tiers and periods
    
    Take the Fubon+ 手機限定 rates (no new fund requirement).
    """
    if not text:
        return None
    
    rates = {}
    
    # First try Fubon+ 手機限定 section
    fubon_idx = text.find('Fubon+ 手機應用程式限定')
    if fubon_idx < 0:
        fubon_idx = text.find('Fubon+手機應用程式限定')
    
    if fubon_idx >= 0:
        fubon_section = text[fubon_idx:fubon_idx+3000]
        
        # Find the highest amount tier (500,000或以上)
        # Rates are in a table: period × amount
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            # Look for rate near the period label
            # Try to find the highest tier's rate
            idx = fubon_section.find(label)
            if idx >= 0:
                # Get nearby percentages
                nearby = fubon_section[idx:idx+200]
                pcts = re.findall(r'(\d+\.\d+)%', nearby)
                if pcts:
                    hkd_rates[period] = max(float(x) for x in pcts)
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
            rates['note'] = 'Fubon+手機應用程式定存利率'
    
    # If no Fubon+ rates, try new fund rates
    if 'hkd' not in rates:
        nf_idx = text.find('新資金定期存款優惠')
        if nf_idx >= 0:
            nf_section = text[nf_idx:nf_idx+2000]
            
            # HKD block
            hkd_idx = nf_section.find('港元', 10)  # skip first occurrence in title
            usd_idx = nf_section.find('美元')
            
            if hkd_idx >= 0:
                end = usd_idx if usd_idx > hkd_idx else hkd_idx + 500
                hkd_block = nf_section[hkd_idx:end]
                pcts = re.findall(r'(\d+\.\d+)%', hkd_block)
                if pcts:
                    rates['hkd'] = {'3m': max(float(x) for x in pcts)}
            
            if usd_idx >= 0:
                usd_block = nf_section[usd_idx:usd_idx+300]
                pcts = re.findall(r'(\d+\.\d+)%', usd_block)
                if pcts:
                    rates['usd'] = {'3m': max(float(x) for x in pcts)}
            
            rates['note'] = '新資金定期存款優惠'
    
    # Also get USD from new fund section if not already present
    if 'usd' not in rates:
        nf_idx = text.find('新資金定期存款優惠')
        if nf_idx >= 0:
            nf_section = text[nf_idx:nf_idx+2000]
            usd_idx = nf_section.find('美元')
            if usd_idx >= 0:
                usd_block = nf_section[usd_idx:usd_idx+300]
                pcts = re.findall(r'(\d+\.\d+)%', usd_block)
                if pcts:
                    rates['usd'] = {'3m': max(float(x) for x in pcts)}
    
    if rates:
        return rates
    return None
