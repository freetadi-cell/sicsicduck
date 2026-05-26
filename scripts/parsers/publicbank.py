"""大眾銀行 Public Bank - Parser for deposit rates."""
import re

def parse(text, tables=None):
    """Parse Public Bank HK deposit rates.
    
    Page has clear table:
    一個月  2.0000%  2.0500%  2.1000%
    三個月  2.4000%  2.4500%  2.5000%
    
    Take the highest tier (>= $500,000).
    
    USD section:
    一個月  3.3000%
    三個月  3.6000%
    """
    if not text:
        return None
    
    rates = {}
    note = '定期存款年利率'
    
    # HKD section - look for rates after "港元定期存款年利率"
    hkd_idx = text.find('港元定期存款年利率')
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx+1500]
        
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            # Find line with this period, take 3rd rate (highest tier >= 500,000)
            pattern = rf'{label}\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%'
            m = re.search(pattern, hkd_section)
            if m:
                hkd_rates[period] = float(m.group(3))  # highest tier
            else:
                # Try with just one rate
                pattern2 = rf'{label}\s+(\d+\.\d+)%'
                m2 = re.search(pattern2, hkd_section)
                if m2:
                    hkd_rates[period] = float(m2.group(1))
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # USD section - look for rates after "外幣定期存款年利率"
    usd_idx = text.find('外幣定期存款年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+2000]
        
        # The USD is the first column in the foreign currency table
        # Headers: 貨幣  美元  日圓  英鎊  澳元  ...
        # We need to find the USD column values
        # Pattern: 一個月  3.3000%  ... (first number after period label)
        usd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, usd_section)
            if m:
                usd_rates[period] = float(m.group(1))
        
        if usd_rates:
            rates['usd'] = usd_rates
    
    if rates:
        rates['note'] = note
        return rates
    return None
