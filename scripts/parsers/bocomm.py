"""交通銀行（香港）BOCOM - Parser for time deposit rates.

Supports two data sources:
1. HKET article (wealth.hket.com) - primary source
2. Bank website (iframes) - backup

HKET article format (table with shared conditions):
存款期  年利率  起存額  條件
1個月  2.45厘  100萬元  理財客戶網上新資金
3個月  2.85厘
1個月  2.15厘  2萬元  電子渠道開立
3個月  2.55厘
6個月  2.75厘
12個月  2.6厘

Note: When condition is missing, it inherits from the previous row.
"""
import re


def parse(text, tables=None, html=None):
    """Parse BOCOM Hong Kong time deposit rates."""
    # Try HKET format first
    if text and '厘' in text and '交通銀行' in text:
        result = _parse_hket(text)
        if result:
            return result
    
    # Fallback to table format (bank website)
    if tables:
        result = _parse_tables(tables)
        if result:
            return result
    
    return None


def _parse_hket(text):
    """Parse HKET article format.
    
    The table has shared conditions: when a condition row appears,
    all subsequent rate rows (until next condition) use that condition.
    """
    rates = {}
    
    # Find the main rate table section
    section_start = text.find('交銀香港')
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
    
    # Current state (condition persists across rows)
    current_condition = 'new_funds'
    current_min_deposit = 1000000
    
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
            if '理財客戶' in next_line:
                current_condition = 'new_funds'
                current_min_deposit = current_min_deposit or 1000000
                j += 1
                continue
            elif '電子渠道' in next_line:
                current_condition = 'existing_funds'
                current_min_deposit = current_min_deposit or 20000
                j += 1
                continue
            
            # Not deposit or condition, stop looking
            break
        
        # Build rate entry
        if current_condition == 'new_funds':
            rate_entry = {
                'rate': rate,
                'min_deposit': current_min_deposit,
                'note': '理財客戶網上新資金',
                'source': 'hket',
                'conditions': ['new_funds', 'wealth_customer']
            }
        else:
            rate_entry = {
                'rate': rate,
                'min_deposit': current_min_deposit,
                'note': '電子渠道開立',
                'source': 'hket',
                'conditions': ['electronic_channel']
            }
        
        # Store rate
        if period_key not in hkd:
            hkd[period_key] = {}
        hkd[period_key][current_condition] = rate_entry
        
        # Move to next row
        i = j
    
    if hkd:
        rates['hkd'] = hkd
    
    if rates:
        return rates
    return None


def _parse_tables(tables):
    """Parse bank website table format."""
    rates = {}
    
    for table in tables:
        table_str = str(table)
        
        if '貨幣' in table_str and '存期' in table_str and '年利率' in table_str:
            lines = [l.strip() for l in table_str.split('\n') if l.strip()]
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                if line in ('HKD', 'USD', 'CNY'):
                    currency = line
                    period = lines[i + 1] if i + 1 < len(lines) else ''
                    rate_str = lines[i + 2] if i + 2 < len(lines) else ''
                    
                    m = re.search(r'(\d+\.\d+)%', rate_str)
                    if m:
                        rate = float(m.group(1))
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
    
    return rates if rates else None


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