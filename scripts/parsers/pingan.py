"""平安數字銀行 PAObank - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Since the official website is blocked by Cloudflare, we use HKET as the primary source.

Last update: 2026-07-10 from HKET
"""
import re


def parse(text, tables=None, html=None):
    """Parse PAObank time deposit rates from HKET article."""
    if not text:
        return None
    
    rates = {}
    lines = text.split('\n')
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Detect section headers
        if '新資金' in line and '現有資金' not in line:
            current_section = 'new_funds'
        elif '現有資金' in line or '不論新舊資金' in line:
            current_section = 'existing_funds'
        elif '新客戶' in line or '新戶' in line:
            current_section = 'new_customer'
        
        # Extract rates from table-like format
        if '%' in line and '厘' in line:
            period_match = re.search(r'(\d+)個月', line)
            rate_match = re.search(r'(\d+\.?\d*)厘', line)
            
            if period_match and rate_match:
                period = f"{period_match.group(1)}m"
                rate = float(rate_match.group(1)) / 100
                
                if 'hkd' not in rates:
                    rates['hkd'] = {}
                
                if period not in rates['hkd']:
                    rates['hkd'][period] = {}
                
                if current_section:
                    rates['hkd'][period][current_section] = {
                        'rate': rate,
                        'min_deposit': 100,
                        'source': 'hket',
                        'note': '新資金' if current_section == 'new_funds' else '不論新舊資金'
                    }
        
        # Parse new customer promotional rate
        if '新客戶' in line and '8%' in line:
            if 'hkd' not in rates:
                rates['hkd'] = {}
            if '1m' not in rates['hkd']:
                rates['hkd']['1m'] = {}
            rates['hkd']['1m']['new_customer'] = {
                'rate': 0.08,
                'min_deposit': 50000,
                'max_deposit': 50000,
                'note': '全新客戶首5萬',
                'source': 'hket',
                'conditions': ['new_customer', 'limited_time']
            }
    
    if rates:
        rates['note'] = '平安數字銀行定期存款（來源：HKET）'
        return rates
    return None