"""工銀亞洲 ICBC Asia - Parser for new funds time deposit rates.

Page: https://www.icbcasia.com/hk/tc/personal/latest-promotion/new-funds-time-deposit.html

Table format:
客戶類別  存款金額          98天     188天
工銀財富客戶  港幣3,000,000元或以上  3.00%    3.00%
...
零售銀行個人客戶 港幣50,000元或以上   2.90%    2.90%
"""
import re


def parse(text, tables=None, html=None):
    """Parse ICBC Asia time deposit rates from page text.
    
    The page may not have tables (JS-rendered), so we parse from text.
    """
    if not text:
        return None
    
    rates = {}
    
    # Check if tables exist and parse them
    if tables:
        for table in tables:
            table_str = str(table)
            if '98天' in table_str and '188天' in table_str:
                hkd_rates = _parse_rates(table_str, '港幣', '零售')
                if hkd_rates:
                    rates['hkd'] = hkd_rates
                
                usd_rates = _parse_rates(table_str, '美元', '零售')
                if usd_rates:
                    rates['usd'] = usd_rates
                
                cny_rates = _parse_rates(table_str, '人民幣', '零售')
                if cny_rates:
                    rates['cny'] = cny_rates
    
    # If no rates from tables, parse from text
    if not rates and text:
        # Look for patterns like "港元定期存款 高達 3.00% 年利率"
        # or "特惠定存年利率5.88%"
        
        # HKD rates
        hkd_match = re.search(r'港元定期存款.*?高達\s*(\d+\.\d+)%', text, re.DOTALL)
        if hkd_match:
            rates['hkd'] = {
                '3m': {
                    'rate': float(hkd_match.group(1)),
                    'min_deposit': 50000,
                    'note': '工銀亞洲網上定期存款優惠',
                    'source': 'bank'
                }
            }
        
        # USD rates
        usd_match = re.search(r'外幣定期存款.*?高達\s*(\d+\.\d+)%', text, re.DOTALL)
        if usd_match:
            rates['usd'] = {
                '3m': {
                    'rate': float(usd_match.group(1)),
                    'min_deposit': 5000,
                    'note': '工銀亞洲外幣定期存款優惠',
                    'source': 'bank'
                }
            }
        
        # Also look for "特惠定存年利率X.XX%"
        promo_match = re.search(r'特惠定存年利率\s*(\d+\.\d+)%', text)
        if promo_match and 'hkd' not in rates:
            rates['hkd'] = {
                '3m': {
                    'rate': float(promo_match.group(1)),
                    'min_deposit': 10000,
                    'note': '工銀亞洲新客戶特惠定期存款',
                    'source': 'bank'
                }
            }
    
    if rates:
        return rates
    return None


def _parse_rates(table_str, currency_marker, tier_marker):
    """Parse rates for a specific currency and tier.
    
    Returns a dict with '3m' key (mapped from 98/188 days).
    """
    rates = {}
    
    lines = table_str.split('\n')
    for line in lines:
        # Look for the line with both currency marker and tier marker
        if currency_marker in line and (tier_marker in line or '零售' in line):
            # Extract the rate
            # Format: 港幣50,000元或以上  2.90%  2.90%
            m = re.search(r'(\d+\.\d+)%\s+(\d+\.\d+)%', line)
            if m:
                # Use 98天 rate as approximate 3m rate
                rates['3m'] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 50000,
                    'note': '工銀亞洲新資金定期存款（98天）',
                    'source': 'bank'
                }
                # Also store 188天 as approximate 6m rate
                rates['6m'] = {
                    'rate': float(m.group(2)),
                    'min_deposit': 50000,
                    'note': '工銀亞洲新資金定期存款（188天）',
                    'source': 'bank'
                }
                break
    
    return rates if rates else None