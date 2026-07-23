"""南洋商業銀行 NCB - Parser for time deposit rates.

Uses HKET as primary data source since official website is JS-rendered.

HKET article format:
- 新資金定期存款優惠
- 各存款期利率
"""
import re


def parse(text, tables=None, html=None):
    """Parse NCB (南洋商業銀行) time deposit rates from HKET article.
    
    Expected format from HKET:
    - 南洋商業銀行新資金定期存款
    - 1個月、3個月、6個月、12個月利率
    """
    if not text:
        return None
    
    rates = {}
    
    # Look for NCB section in HKET article
    # Pattern: 南洋 + 新資金/定期存款
    ncb_markers = ['南洋商業銀行', '南洋商業', 'NCB', 'Nanyang Commercial Bank']
    is_ncb_section = any(marker in text for marker in ncb_markers)
    
    if not is_ncb_section:
        return None
    
    # Extract HKD rates
    hkd_rates = {}
    
    # Pattern 1: "X個月 Y.YY%" or "X個月 Y.YY厘"
    for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Try percentage format
        m = re.search(rf'{label}\s+(\d+\.\d+)%', text)
        if m:
            hkd_rates[period] = {
                'rate': float(m.group(1)),
                'fund_type': 'new_funds',
                'min_deposit': 10000,
                'note': '南洋商業銀行新資金定期存款',
                'source': 'hket'
            }
        else:
            # Try 厘 format (1厘 = 0.01%)
            m = re.search(rf'{label}\s+(\d+\.\d+)厘', text)
            if m:
                hkd_rates[period] = {
                    'rate': float(m.group(1)) / 100,
                    'fund_type': 'new_funds',
                    'min_deposit': 10000,
                    'note': '南洋商業銀行新資金定期存款',
                    'source': 'hket'
                }
    
    # Pattern 2: Table format with currency column
    # Look for section starting with "港元" or "HKD"
    if not hkd_rates:
        hkd_section_match = re.search(r'港元.*?(?=美元|人民幣|CNY|USD|$)', text, re.DOTALL)
        if hkd_section_match:
            hkd_section = hkd_section_match.group(0)
            for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
                m = re.search(rf'{label}\s+(\d+\.\d+)%', hkd_section)
                if m:
                    hkd_rates[period] = {
                        'rate': float(m.group(1)),
                        'fund_type': 'new_funds',
                        'min_deposit': 10000,
                        'note': '南洋商業銀行新資金定期存款',
                        'source': 'hket'
                    }
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    # Extract USD rates
    usd_rates = {}
    usd_section_match = re.search(r'美元.*?(?=港元|人民幣|CNY|HKD|$)', text, re.DOTALL)
    if usd_section_match:
        usd_section = usd_section_match.group(0)
        for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', usd_section)
            if m:
                usd_rates[period] = {
                    'rate': float(m.group(1)),
                    'fund_type': 'new_funds',
                    'min_deposit': 1000,
                    'note': '南洋商業銀行美元定期存款',
                    'source': 'hket'
                }
    
    if usd_rates:
        rates['usd'] = usd_rates
    
    # Extract CNY rates
    cny_rates = {}
    cny_section_match = re.search(r'人民幣.*?(?=港元|美元|HKD|USD|$)', text, re.DOTALL)
    if cny_section_match:
        cny_section = cny_section_match.group(0)
        for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', cny_section)
            if m:
                cny_rates[period] = {
                    'rate': float(m.group(1)),
                    'fund_type': 'new_funds',
                    'min_deposit': 10000,
                    'note': '南洋商業銀行人民幣定期存款',
                    'source': 'hket'
                }
    
    if cny_rates:
        rates['cny'] = cny_rates
    
    return rates if rates else None