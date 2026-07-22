"""螞蟻銀行 Ant Bank - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Since the official website shows 404, we use HKET as the primary source.

Last update: 2026-07-10 from HKET
"""
import re


def parse(text, tables=None, html=None):
    """Parse Ant Bank time deposit rates from HKET article."""
    if not text:
        return None
    
    rates = {}
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Parse table format: 存款期 年利率 起存額 條件
        # 1個月 1.5厘 10萬元 新資金
        if '個月' in line and '厘' in line:
            period_match = re.search(r'(\d+)個月', line)
            rate_match = re.search(r'(\d+\.?\d*)厘', line)
            amount_match = re.search(r'(\d+)萬元', line)
            
            if period_match and rate_match:
                period = f"{period_match.group(1)}m"
                rate = float(rate_match.group(1)) / 100
                min_deposit = int(amount_match.group(1)) * 10000 if amount_match else 1
                
                if 'hkd' not in rates:
                    rates['hkd'] = {}
                
                if period not in rates['hkd']:
                    rates['hkd'][period] = {}
                
                rates['hkd'][period]['new_funds'] = {
                    'rate': rate,
                    'min_deposit': min_deposit,
                    'note': f'新資金，{min_deposit//10000}萬起',
                    'source': 'hket',
                    'conditions': ['new_funds']
                }
    
    if rates:
        rates['note'] = '螞蟻銀行定期存款（來源：HKET）'
        return rates
    return None