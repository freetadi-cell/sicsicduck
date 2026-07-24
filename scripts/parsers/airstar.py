"""象象銀行 EleBank (Airstar) - Parser for time deposit rates.

Updated 2026-07-24: 
- 官網定存利率被 JS 渲染，web_fetch 抓唔到
- 改用 HKET 作為主要數據源
- 保留官網 parser 作為後備

Page: https://www.elebank.com/zh-hk/hkprime.html
HKET: https://wealth.hket.com/article/3909912 (OCBC - 相同格式)
"""
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse EleBank time deposit rates.
    
    Priority:
    1. Try HKET article parsing (hket_common)
    2. Fallback to original table parsing
    """
    if not text:
        return None
    
    # === Try HKET parsing first ===
    # Check if this looks like an HKET article
    if '象象銀行' in text or 'EleBank' in text or '每日定存' in text:
        rates = parse_hket_article(text, bank_name='象象銀行')
        if rates and rates.get('hkd'):
            # Convert HKET format to standard format
            return _convert_hket_to_standard(rates)
    
    # === Fallback: original table parsing ===
    rates = {}
    
    if tables:
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
                                hkd_rates[period_key] = {
                                    'rate': rate,
                                    'min_deposit': 1,
                                    'note': '象象銀行港元定期存款',
                                    'source': 'bank'
                                }
                    
                    if hkd_rates:
                        rates['hkd'] = hkd_rates
    
    if rates:
        return rates
    return None


def _convert_hket_to_standard(hket_rates):
    """Convert HKET format to standard format.
    
    HKET format:
    {
        'bank': '象象銀行',
        'source': 'hket',
        'hkd': {
            '1m': {
                'new_funds': {'rate': 2.95, 'min_deposit': 100000, ...},
                'existing_funds': {'rate': 2.80, 'min_deposit': 100000, ...}
            }
        }
    }
    
    Standard format:
    {
        'hkd': {
            '1m': {'rate': 2.95, 'min_deposit': 100000, 'note': '...', 'source': 'hket'},
            ...
        }
    }
    """
    result = {}
    
    for currency in ['hkd', 'usd', 'cny']:
        if currency not in hket_rates:
            continue
        
        currency_rates = {}
        for period, period_data in hket_rates[currency].items():
            # Take the best rate (new_funds > existing_funds > general)
            best_rate = None
            best_data = None
            
            for fund_type in ['new_funds', 'existing_funds', 'general']:
                if fund_type in period_data:
                    data = period_data[fund_type]
                    rate = data.get('rate', 0)
                    if rate and (best_rate is None or rate > best_rate):
                        best_rate = rate
                        best_data = data
            
            if best_data:
                currency_rates[period] = {
                    'rate': best_data['rate'],
                    'min_deposit': best_data.get('min_deposit', 0),
                    'note': best_data.get('note', '定期存款'),
                    'source': 'hket'
                }
        
        if currency_rates:
            result[currency] = currency_rates
    
    return result if result else None