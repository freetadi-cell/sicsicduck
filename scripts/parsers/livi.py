"""理慧銀行 Livi Bank - Parser for time deposit rates.

Page: https://www.livibank.com/zh_HK/features/livisave.html

Table format (港元定存):
存入金額（HKD）  500 - 5萬以下  5萬+
7 日            0.25%         0.25%
1 個月          0.50%         1.20%
2 個月          0.50%         0.50%
3 個月          1.10%         2.80%
4 個月          1.20%         2.60%
6 個月          1.30%         2.60%
9 個月          1.30%         2.70%
12 個月         1.60%         2.70%

Also has USD and CNY tables.

⚠️ Bug fix (2026-07-25):
- 舊版只解析 1m/3m/6m/12m，漏咗 1w/2m/4m/9m
- 舊版對 1w/2m 嘅解析有 bug，會產出 25%/50% 呢啲異常值
- 新版完整解析所有年期，正確提取兩個檔次嘅利率
"""
import re


def parse(text, tables=None, html=None):
    """Parse Livi Bank time deposit rates."""
    if not tables:
        return None
    
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        # HKD table - must have 存入金額 AND (HKD or 港元)
        if '存入金額' in table_str and ('HKD' in table_str.upper() or '港元' in table_str):
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
    """Parse HKD table, returning both tiers.

    Table format:
    存入金額（HKD）  500 - 5萬以下  5萬+
    7 日            0.25%         0.25%
    1 個月          0.50%         1.20%
    ...
    
    Returns rates for 5萬+ tier (better rates) as main,
    and 500-5萬 tier as existing_funds where different.
    """
    rates = {}
    
    # Complete period mapping including short tenors
    period_map = {
        '7 日': '1w',
        '1 個月': '1m',
        '2 個月': '2m',
        '3 個月': '3m',
        '4 個月': '4m',
        '6 個月': '6m',
        '9 個月': '9m',
        '12 個月': '12m',
    }
    
    lines = table_str.split('\n')
    for line in lines:
        for period_label, period_key in period_map.items():
            if period_label in line:
                # Extract all percentage rates from this line
                # Format: "3 個月  1.10%  2.80%"
                nums = re.findall(r'(\d+\.\d+)%', line)
                
                if len(nums) >= 2:
                    # Two tiers: low tier (500-5萬) and high tier (5萬+)
                    low_rate = float(nums[0])
                    high_rate = float(nums[1])
                    
                    # Use high tier as main rate
                    rates[period_key] = {
                        'rate': high_rate,
                        'min_deposit': 50000,
                        'note': '理慧銀行港元定期存款',
                        'source': 'bank'
                    }
                    
                    # If low tier is different, store as existing_funds
                    if low_rate != high_rate:
                        rates[period_key]['existing_funds'] = {
                            'rate': low_rate,
                            'min_deposit': 500,
                            'note': '理慧銀行港元定期存款',
                            'source': 'bank'
                        }
                        rates[period_key]['new_funds'] = {
                            'rate': high_rate,
                            'min_deposit': 50000,
                            'note': '5萬+利率',
                            'source': 'bank'
                        }
                        # Remove the flat 'rate' key since we have nested structure
                        del rates[period_key]['rate']
                        del rates[period_key]['min_deposit']
                        del rates[period_key]['note']
                        del rates[period_key]['source']
                    
                elif len(nums) == 1:
                    # Single tier
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
                        'note': '理慧銀行美元定期存款',
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
                        'note': '理慧銀行人民幣定期存款',
                        'source': 'bank'
                    }
                break
    
    return rates if rates else None
