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
    """Parse BOCOM Hong Kong time deposit rates."""
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # Look for the rate table with currency and period
        if '貨幣' in table_str and '存期' in table_str and '年利率' in table_str:
            lines = table_str.split('\n')
            
            hkd_rates = {}
            usd_rates = {}
            cny_rates = {}
            
            for line in lines:
                # Look for HKD rates
                if 'HKD' in line and '3個月' in line:
                    m = re.search(r'(\d+\.\d+)%', line)
                    if m:
                        hkd_rates['3m'] = float(m.group(1))
                
                # Look for USD rates
                if 'USD' in line and '3個月' in line:
                    m = re.search(r'(\d+\.\d+)%', line)
                    if m:
                        usd_rates['3m'] = float(m.group(1))
                
                # Look for CNY rates
                if 'CNY' in line and '3個月' in line:
                    m = re.search(r'(\d+\.\d+)%', line)
                    if m:
                        cny_rates['3m'] = float(m.group(1))
            
            if hkd_rates:
                rates['hkd'] = hkd_rates
                rates['hkd']['note'] = '交通銀行港元定期存款'
            
            if usd_rates:
                rates['usd'] = usd_rates
                rates['usd']['note'] = '美元定期存款'
            
            if cny_rates:
                rates['cny'] = cny_rates
                rates['cny']['note'] = '人民幣定期存款'
            
            break
    
    if rates:
        rates['note'] = '交通銀行（香港）定期存款利率'
        return rates
    return None