"""工銀亞洲 ICBC Asia - Parser for online time deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse ICBC Asia online time deposit rates.
    
    Page has structured table:
    貨幣  定期存款金額  1個月  2個月  3個月  6個月  12個月
    港幣  800,000或以上  1.60%  2.20%  2.65%  2.50%  2.50%
    美元  100,000或以上  3.20%  3.35%  3.60%  3.60%  3.60%
    
    Take the highest tier for each currency (工銀財富/理財金).
    """
    if not text:
        return None
    
    rates = {}
    note = '網上銀行特惠利率（工銀財富客戶）'
    
    # Find HKD rates - look for highest tier
    # Pattern: 港幣 <amount> 1.xx% 2.xx% 2.xx% 2.xx% 2.xx%
    # Take the 3,000,000 tier for best rates
    
    # HKD - find line with 3,000,000 or highest available
    hkd_lines = re.findall(r'港\s*幣\s+[\d,]+[^%]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', text)
    if hkd_lines:
        # Take last match (highest tier)
        m = hkd_lines[-1]
        rates['hkd'] = {
            '1m': float(m[0]),
            '3m': float(m[2]),  # skip 2m
            '6m': float(m[3]),
            '12m': float(m[4]),
        }
    
    # USD
    usd_lines = re.findall(r'美\s*元\s+[\d,]+[^%]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', text)
    if usd_lines:
        m = usd_lines[-1]
        rates['usd'] = {
            '1m': float(m[0]),
            '3m': float(m[2]),
            '6m': float(m[3]),
            '12m': float(m[4]),
        }
    
    if rates:
        rates['note'] = note
        return rates
    return None
