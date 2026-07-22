"""象象銀行 EleBank (Airstar) - Parser for time deposit rates.

Updated 2026-07-22: 定存利率在 HK Prime 頁面，非定存專頁。

Page: https://www.elebank.com/zh-hk/hkprime.html

Table format (horizontal):
存款期  1 星期  1 個月  2 個月  3 個月  4 個月  6 個月  9 個月  12 個月
利率    0.01%  1.50%   0.55%   2.55%   2.70%   2.90%   3.05%   3.15%

The rates are in the second row, aligned with period columns.
"""
import re


def parse(text, tables=None, html=None):
    """Parse EleBank time deposit rates from HK Prime page."""
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # Look for the time deposit table (has "存款期" and "利率")
        if '存款期' in table_str and '利率' in table_str:
            lines = table_str.split('\n')
            
            if len(lines) >= 2:
                # First line: header with periods
                # Second line: rates
                header = lines[0]
                values = lines[1] if len(lines) > 1 else ''
                
                # Column mapping - periods and their positions
                period_columns = [
                    ('1 星期', '1w'),
                    ('1 個月', '1m'),
                    ('2 個月', '2m'),
                    ('3 個月', '3m'),
                    ('4 個月', '4m'),
                    ('6 個月', '6m'),
                    ('9 個月', '9m'),
                    ('12 個月', '12m'),
                ]
                
                hkd_rates = {}
                
                # Extract all rates from the values line
                rate_matches = re.findall(r'(\d+\.\d+)%', values)
                
                # Map rates to periods by position
                for i, (period_label, period_key) in enumerate(period_columns):
                    if period_label in header and i < len(rate_matches):
                        rate = float(rate_matches[i])
                        if rate > 0.01:  # Filter out very low rates
                            hkd_rates[period_key] = rate
                
                if hkd_rates:
                    rates['hkd'] = hkd_rates
                    rates['hkd']['note'] = '象象銀行港元定期存款'
    
    if rates:
        rates['note'] = '象象銀行定期存款利率'
        return rates
    return None