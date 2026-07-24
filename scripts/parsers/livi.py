"""理慧銀行 Livi Bank - Parser for time deposit rates.

Page: https://www.livibank.com/zh_HK/features/livisave.html

Format in markdown:
## 存款期及年利率 (HKD)
存入金額（HKD） 500 - 5萬以下 5萬+
7 日 0.25% 0.25%
1 個月 0.50% 1.20%
3 個月 1.10% 2.80%
6 個月 1.30% 2.60%
12 個月 1.60% 2.70%

## 存款期及年利率 (USD)
1個月 1.50%
3個月 3.90%
6個月 3.40%
12個月 3.30%

## 存款期及年利率 (CNY)
1個月 1.00%
3個月 1.10%
6個月 1.10%
12個月 1.30%
"""
import re


def parse(text, tables=None, html=None):
    """Parse Livi Bank time deposit rates."""
    if not text:
        return None
    
    rates = {}
    
    # === HKD ===
    hkd_idx = text.find('存款期及年利率 (HKD)')
    if hkd_idx < 0:
        hkd_idx = text.find('存款期及年利率')
    
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx + 1000]
        hkd_rates = _parse_hkd_section(hkd_section)
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # === USD ===
    usd_idx = text.find('存款期及年利率 (USD)')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx + 1000]
        usd_rates = _parse_usd_cny_section(usd_section)
        if usd_rates:
            rates['usd'] = usd_rates
    
    # === CNY ===
    cny_idx = text.find('存款期及年利率 (CNY)')
    if cny_idx >= 0:
        cny_section = text[cny_idx:cny_idx + 1000]
        cny_rates = _parse_usd_cny_section(cny_section)
        if cny_rates:
            rates['cny'] = cny_rates
    
    if rates:
        return rates
    return None


def _parse_hkd_section(section):
    """Parse HKD section with tier rates.
    
    Format:
    存入金額（HKD） 500 - 5萬以下 5萬+
    7 日 0.25% 0.25%
    1 個月 0.50% 1.20%
    3 個月 1.10% 2.80%
    6 個月 1.30% 2.60%
    12 個月 1.60% 2.70%
    """
    rates = {}
    
    period_map = {
        '7 日': '1w',
        '7日': '1w',
        '1 個月': '1m',
        '1個月': '1m',
        '3 個月': '3m',
        '3個月': '3m',
        '6 個月': '6m',
        '6個月': '6m',
        '12 個月': '12m',
        '12個月': '12m',
    }
    
    lines = section.split('\n')
    for line in lines:
        # Check if line contains a period
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


def _parse_usd_cny_section(section):
    """Parse USD/CNY section (single tier).
    
    Format:
    1個月 1.50%
    3個月 3.90%
    6個月 3.40%
    12個月 3.30%
    """
    rates = {}
    
    period_map = {
        '1個月': '1m',
        '3個月': '3m',
        '6個月': '6m',
        '12個月': '12m',
    }
    
    lines = section.split('\n')
    for line in lines:
        for period_label, period_key in period_map.items():
            if period_label in line:
                m = re.search(r'(\d+\.\d+)%', line)
                if m:
                    rates[period_key] = {
                        'rate': float(m.group(1)),
                        'min_deposit': 100,
                        'note': '定期存款',
                        'source': 'bank'
                    }
                break
    
    return rates if rates else None