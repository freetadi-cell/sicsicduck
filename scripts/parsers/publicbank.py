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
        hkd_section = text[hkd_idx:hkd_idx+1500]
        
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%'
            m = re.search(pattern, hkd_section)
            if m:
                hkd_rates[period] = {
                    'rate': float(m.group(3)),
                    'min_deposit': 500000,
                    'note': note,
                    'source': 'bank'
                }
            else:
                pattern2 = rf'{label}\s+(\d+\.\d+)%'
                m2 = re.search(pattern2, hkd_section)
                if m2:
                    hkd_rates[period] = {
                        'rate': float(m2.group(1)),
                        'min_deposit': 10000,
                        'note': note,
                        'source': 'bank'
                    }
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # USD section - look for rates after "外幣定期存款年利率"
    usd_idx = text.find('外幣定期存款年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+2000]
        
        usd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, usd_section)
            if m:
                usd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 2000,
                    'note': note,
                    'source': 'bank'
                }
        
        if usd_rates:
            rates['usd'] = usd_rates
    
    # CNY section - look for "人民幣定期存款年利率" or in foreign currency table
    cny_idx = text.find('人民幣定期存款年利率')
    if cny_idx >= 0:
        cny_section = text[cny_idx:cny_idx+1500]
        
        cny_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, cny_section)
            if m:
                cny_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 10000,
                    'note': note,
                    'source': 'bank'
                }
        
        if cny_rates:
            rates['cny'] = cny_rates
    else:
        # Try foreign currency table - CNY may be in a column
        fc_idx = text.find('外幣定期存款年利率')
        if fc_idx >= 0:
            fc_section = text[fc_idx:fc_idx+3000]
            # Look for CNY column header
            cny_col_idx = fc_section.find('人民幣')
            if cny_col_idx >= 0:
                # Extract CNY rates from the column
                cny_rates = {}
                for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
                    # Find the line with this period
                    line_m = re.search(rf'{label}.*', fc_section)
                    if line_m:
                        line = line_m.group(0)
                        # Get all percentages in the line
                        pcts = re.findall(r'(\d+\.\d+)%', line)
                        # CNY is typically in a specific column position
                        # This is approximate - exact position varies
                        if len(pcts) >= 2:
                            cny_rates[period] = {
                                'rate': float(pcts[1]),
                                'min_deposit': 10000,
                                'note': note,
                                'source': 'bank'
                            }
                
                if cny_rates:
                    rates['cny'] = cny_rates
    
    if rates:
        return rates
    return None