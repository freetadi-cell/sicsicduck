"""創興銀行 Chong Hing Bank - Parser for 雲利率 (e-rate / cloud rates).

Updated 2026-07-22 to handle both 雲利率 and 牌價 rates from scraped tables.

Page: https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml

Two rate types:
1. 雲利率 (e-rate) - for online/mobile banking, better rates
2. 牌價 (board rate) - standard rates
"""
import re
import logging

logger = logging.getLogger(__name__)


def parse(text=None, tables=None, html=None):
    """Parse Chong Hing Bank 雲利率 from scraped tables."""
    if not tables:
        return None
    
    rates = {}
    
    # Find the 雲利率 table
    for table in tables:
        table_str = str(table)
        
        # 雲利率 table has distinctive format with higher rates
        # HKD: 3個月 2.60%, 6個月 1.50%, 12個月 0.80-0.95%
        # USD: 3個月 3.60-3.80%, 6個月 3.90%
        # CNY: 3個月 1.00%, 6個月 1.35%, 12個月 1.20%
        
        if '定期存款（雲利率）' in table_str or '港元' in table_str and '3個月' in table_str:
            # Check if this is HKD, USD, or CNY section
            if '港 元' in table_str:
                hkd_rates = _parse_cloud_rates(table_str, '港 元')
                if hkd_rates:
                    rates['hkd'] = hkd_rates
            
            if '美 元' in table_str:
                usd_rates = _parse_cloud_rates(table_str, '美 元')
                if usd_rates:
                    rates['usd'] = usd_rates
            
            if '人民幣' in table_str:
                cny_rates = _parse_cloud_rates(table_str, '人民幣')
                if cny_rates:
                    rates['cny'] = cny_rates
    
    if rates:
        return rates
    
    # Fallback to 牌價 rates
    for table in tables:
        table_str = str(table)
        if '定期存款（牌價）' in table_str:
            if '港 元' in table_str:
                hkd_rates = _parse_board_rates(table_str, '港 元')
                if hkd_rates:
                    rates['hkd'] = hkd_rates
    
    return rates if rates else None


def _parse_cloud_rates(table_str, currency_label):
    """Parse 雲利率 for a specific currency.
    
    Format: 港 元 5,000 至 49,999 0.0010 0.0100 0.0100 2.4500 2.5000 2.6000 1.5000 0.9000 0.8000 0.2000
    Columns: 1天 7天 14天 1個月 2個月 3個月 6個月 9個月 12個月 24個月
    
    Note: Numbers are often concatenated (e.g., "0.00100.0100")
    Solution: Extract 4-decimal numbers (X.XXXX format)
    """
    rates = {}
    
    # Find the currency section
    idx = table_str.find(currency_label)
    if idx < 0:
        return None
    
    # Get the section after currency label
    section = table_str[idx:idx+1500]
    
    # Extract 4-decimal numbers (利率都是 4 位小數)
    # Pattern: X.XXXX where X is digit
    nums = re.findall(r'\d+\.\d{4}', section)
    values = [float(n) for n in nums if float(n) > 0 and float(n) < 100]
    
    # Column indices for periods (0-indexed from rate values)
    # Columns: 1天 7天 14天 1個月 2個月 3個月 6個月 9個月 12個月
    # Skip the first 3 values (1天 7天 14天 are usually very low like 0.0010, 0.0100)
    period_map = {
        '3m': 5,   # 3個月
        '6m': 6,   # 6個月
        '12m': 8,  # 12個月
    }
    
    # Extract rates for each period
    for period, col_idx in period_map.items():
        if col_idx < len(values):
            rate = values[col_idx]
            if rate > 0.5:  # Reasonable rate threshold
                rates[period] = {
                    'rate': rate,
                    'min_deposit': 5000,
                    'note': '雲利率（網上/流動理財）',
                    'source': 'bank'
                }
    
    return rates if rates else None


def _parse_board_rates(table_str, currency_label):
    """Parse 牌價 rates (standard rates)."""
    rates = {}
    
    # Similar logic but for board rates which are lower
    idx = table_str.find(currency_label)
    if idx < 0:
        return None
    
    section = table_str[idx:idx+2000]
    
    # Look for pattern: 港 元 5,000 至 99,999 0.0010 0.0100 0.0100 0.1000 0.1000 0.1200 ...
    # We want 3m, 6m, 12m
    m = re.search(r'(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', section)
    if m:
        # These are 1天 7天 14天 1個月 2個月 3個月
        rates['3m'] = {
            'rate': float(m.group(6)),
            'min_deposit': 5000,
            'note': '定期存款牌價利率',
            'source': 'bank'
        }
    
    return rates if rates else None