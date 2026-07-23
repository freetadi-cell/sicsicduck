"""理慧銀行 Livi Bank - Parser for time deposit rates.

Page: https://www.livibank.com/zh_HK/features/livisave.html

Table format (港元定存):
存入金額（HKD）  500 - 5萬以下  5萬+
7 日            0.25%         0.25%
1 個月          0.50%         1.20%
3 個月          1.10%         2.80%
6 個月          1.30%         2.60%
12 個月         1.60%         2.70%

Also has USD and CNY tables.
"""
import re


def parse(text, tables=None, html=None):
    """Parse Livi Bank time deposit rates."""
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # HKD table
        if '存入金額' in table_str and 'HKD' in table_str.upper():
            hkd_rates = _parse_hkd_table(table_str)
            if hkd_rates:
                rates['hkd'] = hkd_rates
        
        # USD table
        if '美元' in table_str and '100或以上' in table_str:
            usd_rates = _parse_usd_table(table_str)
            if usd_rates:
                rates['usd'] = usd_rates
        
        # CNY table
        if '人民幣' in table_str and '500或以上' in table_str:
            cny_rates = _parse_cny_table(table_str)
            if cny_rates:
                rates['cny'] = cny_rates
    
    if rates:
        return rates
    return None


def _parse_hkd_table(table_str):
    """Parse HKD table, returning best rates (5萬+ tier)."""
    rates = {}
    
    period_map = {
        '1 個月': '1m',
        '3 個月': '3m',
        '6 個月': '6m',
        '12 個月': '12m',
    }
    
    lines = table_str.split('\n')
    for line in lines:
        for period_label, period_key in period_map.items():
            if period_label in line:
                # Extract rates from this line
                # Format: 3 個月  1.10%  2.80%
                nums = re.findall(r'(\d+\.\d+)%', line)
                if len(nums) >= 2:
                    # Take the second rate (5萬+ tier)
                    rates[period_key] = {
                        'rate': float(nums[1]),
                        'min_deposit': 50000,
                        'note': '理慧銀行港元定期存款',
                        'source': 'bank'
                    }
                elif len(nums) == 1:
                    rates[period_key] = {
                        'rate': float(nums[0]),
                        'min_deposit': 500,
                        'note': '理慧銀行港元定期存款',
                        'source': 'bank'
                    }
                break
    
    return rates if rates else None


def _parse_usd_table(table_str):
    """Parse USD table."""
    rates = {}
    
    period_map = {
        '1個月': '1m',
        '3個月': '3m',
        '6個月': '6m',
        '12個月': '12m',
    }
    
    lines = table_str.split('\n')
    for line in lines:
        for period_label, period_key in period_map.items():
            if period_label in line:
                m = re.search(r'(\d+\.\d+)%', line)
                if m:
                    rates[period_key] = {
                        'rate': float(m.group(1)),
                        'min_deposit': 100,
                        'note': '美元定期存款',
                        'source': 'bank'
                    }
                break
    
    return rates if rates else None


def _parse_cny_table(table_str):
    """Parse CNY table."""
    rates = {}
    
    period_map = {
        '1個月': '1m',
        '3個月': '3m',
        '6個月': '6m',
        '12個月': '12m',
    }
    
    lines = table_str.split('\n')
    for line in lines:
        for period_label, period_key in period_map.items():
            if period_label in line:
                m = re.search(r'(\d+\.\d+)%', line)
                if m:
                    rates[period_key] = {
                        'rate': float(m.group(1)),
                        'min_deposit': 500,
                        'note': '人民幣定期存款',
                        'source': 'bank'
                    }
                break
    
    return rates if rates else None