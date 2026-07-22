"""富融銀行 Fusion Bank - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Since the official website is blocked by EdgeOne, we use HKET as the primary source.

Last update: 2026-07-10 from HKET
"""
import re


def parse(text, tables=None, html=None):
    """Parse Fusion Bank time deposit rates from HKET article.
    
    Expected format from HKET:
    - 零元起存: 1周 1.0%, 1月 1.6%, 3月 2.7%, 6月 3.0%, 12月 2.9%
    - 快閃星期一: 1周 6.88%, 新客1月 25.0%, 12月 3.1%
    """
    if not text:
        return None
    
    rates = {}
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Parse standard rates (零元起存)
        if '零元起存' in line or ('不論新舊資金' in line and '%' in line):
            # Extract rates from table-like format
            # Pattern: 1星期 1.0厘 不設最低存款額
            period_match = re.search(r'(\d+)個月|(\d+)星期', line)
            rate_match = re.search(r'(\d+\.?\d*)厘', line)
            
            if period_match and rate_match:
                if period_match.group(1):  # 個月
                    period = f"{period_match.group(1)}m"
                else:  # 星期
                    period = f"{period_match.group(2)}w"
                
                rate = float(rate_match.group(1)) / 100
                
                if 'hkd' not in rates:
                    rates['hkd'] = {}
                
                if period not in rates['hkd']:
                    rates['hkd'][period] = {}
                
                rates['hkd'][period]['general'] = {
                    'rate': rate,
                    'min_deposit': 0,
                    'note': '零元起存',
                    'source': 'hket'
                }
        
        # Parse flash Monday rates (快閃星期一)
        if '快閃' in line and '%' in line:
            # Extract rate
            rate_match = re.search(r'(\d+\.?\d*)%', line)
            if rate_match:
                rate = float(rate_match.group(1)) / 100
                
                # Determine period
                if '1星期' in line or '1周' in line:
                    period = '1w'
                elif '1個月' in line or '1月' in line:
                    period = '1m'
                elif '12個月' in line or '12月' in line:
                    period = '12m'
                else:
                    period = None
                
                if period:
                    if 'hkd' not in rates:
                        rates['hkd'] = {}
                    
                    if period not in rates['hkd']:
                        rates['hkd'][period] = {}
                    
                    # Check if new customer exclusive
                    if '新客' in line or '新戶' in line:
                        rates['hkd'][period]['flash_monday_new_customer'] = {
                            'rate': rate,
                            'note': '快閃星期一新客戶專有',
                            'source': 'hket',
                            'conditions': ['flash_monday', 'new_customer', 'limited_quota']
                        }
                    else:
                        rates['hkd'][period]['flash_monday'] = {
                            'rate': rate,
                            'note': '快閃星期一',
                            'source': 'hket',
                            'conditions': ['flash_monday', 'limited_quota']
                        }
        
        # Parse USD rates
        if '美元定存' in line and '%' in line:
            rate_match = re.search(r'(\d+\.?\d*)%', line)
            period_match = re.search(r'(\d+)個月', line)
            
            if rate_match and period_match:
                rate = float(rate_match.group(1)) / 100
                period = f"{period_match.group(1)}m"
                
                if 'usd' not in rates:
                    rates['usd'] = {}
                
                if period not in rates['usd']:
                    rates['usd'][period] = {}
                
                rates['usd'][period]['flash_monday'] = {
                    'rate': rate,
                    'note': '美元快閃星期一',
                    'source': 'hket',
                    'conditions': ['flash_monday', 'limited_quota']
                }
    
    if rates:
        rates['note'] = '富融銀行定期存款（來源：HKET）'
        return rates
    return None