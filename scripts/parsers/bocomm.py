"""交通銀行（香港）BOCOM - Parser for time deposit rates.

Page: https://www.hk.bankcomm.com/hk/shtml/hk/tw/2005155/2005178/2005179/list.shtml

Table format:
貨幣  存期    年利率
USD   3個月   3.70%
HKD   3個月   2.85%
CNY   3個月   1.35%
"""
import re


def parse(text, tables=None, html=None):
    """Parse BOCOM Hong Kong time deposit rates.
    
    Table format: 貨幣 / 存期 / 年利率 喺唔同行（tab-separated cells）
    Example:
      USD
      6個月
      3.70%
    """
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # Look for the rate table with currency and period
        if '貨幣' in table_str and '存期' in table_str and '年利率' in table_str:
            # The table has currency, period, rate on separate lines
            # Strategy: find all (currency, period, rate) triples
            lines = [l.strip() for l in table_str.split('\n') if l.strip()]
            
            # Skip header lines
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # Check if this line is a currency code
                if line in ('HKD', 'USD', 'CNY'):
                    currency = line
                    # Next line should be the period
                    period = lines[i + 1] if i + 1 < len(lines) else ''
                    # Next line should be the rate
                    rate_str = lines[i + 2] if i + 2 < len(lines) else ''
                    
                    # Extract rate percentage
                    m = re.search(r'(\d+\.\d+)%', rate_str)
                    if m:
                        rate = float(m.group(1))
                        # Map period to key
                        period_key = _map_period(period)
                        if period_key:
                            currency_key = currency.lower()
                            if currency_key not in rates:
                                rates[currency_key] = {}
                            rates[currency_key][period_key] = {
                                'rate': rate,
                                'min_deposit': 10000,
                                'note': f'交通銀行{currency}定期存款',
                                'source': 'bank'
                            }
                    i += 3
                else:
                    i += 1
            
            if rates:
                break
    
    if rates:
        return rates
    return None


def _map_period(period_str):
    """Map Chinese period string to key."""
    mapping = {
        '1個月': '1m',
        '2個月': '2m',
        '3個月': '3m',
        '6個月': '6m',
        '9個月': '9m',
        '12個月': '12m',
    }
    return mapping.get(period_str, None)