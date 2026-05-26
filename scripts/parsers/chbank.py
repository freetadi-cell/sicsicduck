"""創興銀行 Chong Hing Bank - Parser for 雲利率 (cloud rates)."""
import re

def parse(text, tables=None):
    """Parse Chong Hing Bank 雲利率 from tables.
    
    The 雲利率 table has lots of tabs/newlines from HTML formatting.
    After cleanup, data is like: 港 元5,000 至 49,9990.0010...
    Target tier: HKD 500,000-50,000,000 / USD 10,000-6,000,000
    """
    if not tables:
        return None
    
    rates = {}
    note = '雲利率（網上/流動理財）'
    
    # Find the 雲利率 table
    cloud_table = None
    for t in tables:
        if '雲利率' in t:
            cloud_table = t
            break
    
    if not cloud_table:
        return None
    
    # Clean up: remove excess whitespace but keep meaningful content
    cleaned = re.sub(r'\s+', '', cloud_table)  # Remove ALL whitespace
    
    # HKD: target tier "500,000至50,000,000"
    hkd_match = re.search(
        r'港元.*?500,000至50,000,000'
        r'(\d+\.\d+)'   # 1天
        r'(\d+\.\d+)'   # 7天
        r'(\d+\.\d+)'   # 14天
        r'(\d+\.\d+)'   # 1個月
        r'(\d+\.\d+)'   # 2個月
        r'(\d+\.\d+)'   # 3個月
        r'(\d+\.\d+)'   # 6個月
        r'(\d+\.\d+)'   # 9個月
        r'(\d+\.\d+)'   # 12個月
        r'(\d+\.\d+)',   # 24個月
        cleaned
    )
    
    if hkd_match:
        nums = [float(hkd_match.group(i)) for i in range(1, 11)]
        rates['hkd'] = {
            '1m': nums[3],
            '3m': nums[5],
            '6m': nums[6],
            '12m': nums[8],
        }
    
    # USD: target tier "10,000至6,000,000"
    usd_match = re.search(
        r'美元.*?10,000至6,000,000'
        r'(\d+\.\d+)'   # 1天
        r'(\d+\.\d+)'   # 7天
        r'(\d+\.\d+)'   # 14天
        r'(\d+\.\d+)'   # 1個月
        r'(\d+\.\d+)'   # 2個月
        r'(\d+\.\d+)'   # 3個月
        r'(\d+\.\d+)'   # 6個月
        r'(\d+\.\d+)'   # 9個月
        r'(\d+\.\d+)',   # 12個月
        cleaned
    )
    
    if usd_match:
        nums = [float(usd_match.group(i)) for i in range(1, 10)]
        rates['usd'] = {
            '1m': nums[3],
            '3m': nums[5],
            '6m': nums[6],
            '12m': nums[8],
        }
    
    if rates:
        rates['note'] = note
        return rates
    return None
