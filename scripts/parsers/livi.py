"""理慧銀行 Livi Bank - Parser for time deposit rates.

Updated 2026-07-24 to handle text format from requests.

Format:
存款期及年利率 (HKD)
存入金額（HKD） 500 - 5萬以下 5萬+
7 日 0.25% 0.25%
1 個月 0.50% 1.20%
3 個月 1.10% 2.80%
6 個月 1.30% 2.60%
12 個月 1.60% 2.70%
"""
import re


def parse(text, tables=None, html=None):
    """Parse Livi Bank time deposit rates."""
    if not text:
        return None
    
    rates = {}
    
    # === HKD ===
    # Find "存款期及年利率 (HKD)" section
    hkd_idx = text.find('存款期及年利率 (HKD)')
    if hkd_idx >= 0:
        section = text[hkd_idx:hkd_idx + 1000]
        
        # Parse tier rates
        # Format: "1 個月 0.50% 1.20%" (low tier, high tier)
        hkd_rates = {}
        
        for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
            # Match: "1 個月 0.50% 1.20%"
            m = re.search(rf'{label}\s*個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
            if m:
                # Use high tier rate (for 5萬+)
                hkd_rates[period] = {
                    'rate': float(m.group(2)),
                    'min_deposit': 50000,
                    'note': '理慧銀行港元定期存款',
                    'source': 'bank'
                }
        
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # === USD ===
    usd_idx = text.find('存款期及年利率 (USD)')
    if usd_idx >= 0:
        section = text[usd_idx:usd_idx + 1000]
        
        usd_rates = {}
        for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
            m = re.search(rf'{label}\s*個月\s+(\d+\.\d+)%', section)
            if m:
                usd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 10000,
                    'note': '理慧銀行美元定期存款',
                    'source': 'bank'
                }
        
        if usd_rates:
            rates['usd'] = usd_rates
    
    # === CNY ===
    cny_idx = text.find('存款期及年利率 (CNY)')
    if cny_idx >= 0:
        section = text[cny_idx:cny_idx + 1000]
        
        cny_rates = {}
        for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
            m = re.search(rf'{label}\s*個月\s+(\d+\.\d+)%', section)
            if m:
                cny_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 10000,
                    'note': '理慧銀行人民幣定期存款',
                    'source': 'bank'
                }
        
        if cny_rates:
            rates['cny'] = cny_rates
    
    return rates if rates else None
