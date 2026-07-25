"""招商永隆 Wing Lung Bank - Parser for time deposit rates.

Supports two data sources:
1. HKET article (wealth.hket.com) - primary source
2. Bank website (dynamically loaded tables) - backup

HKET article format (table with shared conditions):
存款期  年利率  起存額  條件
1個月  1.15厘  50萬元  手機銀行開立，不論新舊資金
2個月  1.45厘
3個月  2.0厘
6個月  2.0厘
9個月  2.0厘
12個月  2.0厘
24個月  0.15厘

Note: When condition/deposit is missing, it inherits from the previous row.
"""
import re


def parse(text, tables=None, html=None):
    """Parse Wing Lung Bank time deposit rates."""
    # Try HKET format first
    if text and '厘' in text and ('招商永隆' in text or '永隆' in text):
        result = _parse_hket(text)
        if result:
            return result
    
    # Fallback to table format (bank website)
    if tables:
        result = _parse_tables(tables)
        if result:
            return result
    
    if text:
        return _parse_text(text)
    
    return None


def _parse_hket(text):
    """Parse HKET article format.
    
    The table has shared conditions: when a condition/deposit row appears,
    all subsequent rate rows (until next condition) use that condition.
    """
    rates = {}
    
    section_start = text.find('招商永隆銀行')
    if section_start < 0:
        section_start = text.find('存款期')
    
    if section_start < 0:
        return None
    
    section_end = text.find('資料來源', section_start)
    if section_end < 0:
        for end_marker in ['港元定存｜', 'Mox Bank', 'Ant Bank']:
            idx = text.find(end_marker, section_start + 500)
            if idx >= 0 and (section_end < 0 or idx < section_end):
                section_end = idx
        if section_end < 0:
            section_end = len(text)
    
    section = text[section_start:section_end]
    
    hkd = {}
    lines = [l.strip() for l in section.split('\n') if l.strip()]
    
    # Current state (persists across rows)
    current_condition = 'general'
    current_min_deposit = 10000
    current_note = '手機銀行開立，不論新舊資金'
    
    i = 0
    # Skip header
    while i < len(lines) and lines[i] in ['存款期', '年利率', '起存額', '條件']:
        i += 1
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a period line
        period_match = re.match(r'^(\d+)\s*個月$', line)
        if not period_match:
            i += 1
            continue
        
        period_num = int(period_match.group(1))
        period_key = f'{period_num}m'
        
        # Next line should be the rate
        if i + 1 >= len(lines):
            i += 1
            continue
        
        rate_line = lines[i + 1]
        rate_match = re.search(r'(\d+\.?\d*)厘', rate_line)
        if not rate_match:
            i += 1
            continue
        
        rate = float(rate_match.group(1))
        
        # Check if next lines contain deposit and condition
        j = i + 2
        while j < len(lines):
            next_line = lines[j]
            
            # Check if it's a min deposit
            deposit_wan = re.match(r'^(\d+)萬元$', next_line)
            deposit_yuan = re.match(r'^(\d+)元$', next_line)
            if deposit_wan:
                current_min_deposit = int(deposit_wan.group(1)) * 10000
                j += 1
                continue
            elif deposit_yuan:
                current_min_deposit = int(deposit_yuan.group(1))
                j += 1
                continue
            
            # Check if it's a condition
            if '手機銀行' in next_line or '手機App' in next_line or '不論新舊資金' in next_line:
                current_condition = 'general'
                current_note = '手機銀行開立，不論新舊資金'
                j += 1
                continue
            elif '新資金' in next_line:
                current_condition = 'new_funds'
                current_note = '新資金定期存款'
                j += 1
                continue
            
            # Not deposit or condition, stop looking
            break
        
        # Build rate entry
        hkd[period_key] = {
            'rate': rate,
            'min_deposit': current_min_deposit,
            'note': current_note,
            'source': 'hket',
            'conditions': ['mobile_banking'] if '手機' in current_note else []
        }
        
        # Move to next row
        i = j
    
    if hkd:
        rates['hkd'] = hkd
    
    if rates:
        return rates
    return None


def _parse_currency_table(tables, table_marker):
    """Parse rates from a specific currency table (bank website format)."""
    rates = {}
    
    for table in tables:
        table_str = str(table)
        if table_marker in table_str:
            lines = table_str.split('\n')
            
            current_period = None
            period_numbers = {'1m': [], '3m': [], '6m': [], '12m': []}
            
            for line in lines:
                if '1 個月' in line:
                    current_period = '1m'
                elif '3 個月' in line:
                    current_period = '3m'
                elif '6 個月' in line:
                    current_period = '6m'
                elif '12 個月' in line:
                    current_period = '12m'
                
                if current_period:
                    nums = re.findall(r'(\d+\.\d+)', line)
                    for num in nums:
                        val = float(num)
                        if val > 0.1:
                            period_numbers[current_period].append(val)
            
            for period_key, numbers in period_numbers.items():
                if numbers:
                    for num in reversed(numbers):
                        if num >= 1.0:
                            rates[period_key] = {
                                'rate': num,
                                'min_deposit': 50000,
                                'note': '招商永隆銀行手機App優惠定存利率',
                                'source': 'bank'
                            }
                            break
            
            break
    
    return rates if rates else None


def _parse_tables(tables):
    """Parse bank website table format."""
    rates = {}
    
    hkd_rates = _parse_currency_table(tables, '港元定期存款利率')
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    usd_rates = _parse_currency_table(tables, '美元定期存款利率')
    if usd_rates:
        rates['usd'] = usd_rates
    
    cny_rates = _parse_currency_table(tables, '人民幣定期存款利率')
    if cny_rates:
        rates['cny'] = cny_rates
    
    return rates if rates else None


def _parse_text(text):
    """Fallback text parsing (less reliable)."""
    if not text:
        return None
    
    rates = {}
    
    for period, label in [('1m', '1 個月'), ('3m', '3 個月'), 
                           ('6m', '6 個月'), ('12m', '12 個月')]:
        idx = text.find(label)
        if idx >= 0:
            section = text[idx:idx+300]
            nums = re.findall(r'(\d+\.\d+)', section)
            if nums:
                for num in reversed(nums):
                    rate = float(num)
                    if rate >= 1.0:
                        rates[period] = {
                            'rate': rate,
                            'min_deposit': 50000,
                            'note': '招商永隆銀行手機App優惠定存利率',
                            'source': 'bank'
                        }
                        break
    
    if rates:
        return {'hkd': rates}
    return None