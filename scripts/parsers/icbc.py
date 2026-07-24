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
    """Parse ICBC Asia new funds time deposit rates."""
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # Check if this is the main rate table
        if '98天' in table_str and '188天' in table_str:
            # Parse HKD rates (零售銀行個人客戶 tier)
            hkd_rates = _parse_rates(table_str, '港幣', '零售')
            if hkd_rates:
                rates['hkd'] = hkd_rates
            
            # Parse USD rates
            usd_rates = _parse_rates(table_str, '美元', '零售')
            if usd_rates:
                rates['usd'] = usd_rates
            
            # Parse CNY rates
            cny_rates = _parse_rates(table_str, '人民幣', '零售')
            if cny_rates:
                rates['cny'] = cny_rates
    
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