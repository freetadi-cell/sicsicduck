"""南洋商業銀行 NCB - Parser for time deposit rates.

Data source: HKET wealth.hket.com article
URL: https://wealth.hket.com/article/3909866

The HKET article format for NCB includes:
- 新客戶專享定期存款 rates
- 「多元配置，多元賞息」推廣 rates
- 全新理財客戶 rates
- General 定期存款 rates (電子渠道新資金)

Table format:
存款期  年利率  起存額  條件
1星期  6.8厘  1000元  兌換資金開立
1個月  2.88厘
1個月  2.5厘  1萬元  電子渠道新資金
3個月  2.85厘
6個月  3.05厘
12個月  3.05厘
"""
import re


def parse(text, tables=None, html=None):
    """Parse NCB (南洋商業銀行) time deposit rates from HKET article.
    
    The article contains multiple rate tables for different conditions.
    We extract the main promotional rates (電子渠道新資金) as primary,
    and special rates (兌換資金, 新客戶) as additional entries.
    """
    if not text:
        return None
    
    rates = {}
    
    # Find the main rate table section
    section_start = text.find('南洋商業銀行')
    if section_start < 0:
        section_start = text.find('存款期')
    
    if section_start < 0:
        return None
    
    section_end = text.find('資料來源', section_start)
    if section_end < 0:
        section_end = len(text)
    
    section = text[section_start:section_end]
    
    hkd = {}
    
    lines = section.split('\n')
    current_condition = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect condition from line
        if '兌換資金' in line:
            current_condition = 'exchange'
        elif '電子渠道新資金' in line or '新資金' in line:
            current_condition = 'new_funds'
        elif '新客戶' in line:
            current_condition = 'new_customer'
        elif '不論新舊資金' in line:
            current_condition = 'existing_funds'
        
        # Extract period and rate
        period_match = re.search(r'(\d+)\s*(個月|星期|周)', line)
        if not period_match:
            continue
        
        period_num = int(period_match.group(1))
        period_unit = period_match.group(2)
        
        if period_unit in ['星期', '周']:
            period_key = f'{period_num}w'
        else:
            period_key = f'{period_num}m'
        
        # Extract rate (厘 format)
        rate_match = re.search(r'(\d+\.?\d*)厘', line)
        if not rate_match:
            continue
        
        rate = float(rate_match.group(1))
        
        # Extract min deposit
        min_deposit = 0
        deposit_wan = re.search(r'(\d+)萬元', line)
        deposit_yuan = re.search(r'(\d+)元', line)
        if deposit_wan:
            min_deposit = int(deposit_wan.group(1)) * 10000
        elif deposit_yuan:
            min_deposit = int(deposit_yuan.group(1))
        
        # Build rate entry
        if current_condition == 'exchange':
            rate_entry = {
                'rate': rate,
                'min_deposit': min_deposit or 1000,
                'note': '兌換資金開立',
                'source': 'hket',
                'conditions': ['exchange']
            }
        elif current_condition == 'new_funds':
            rate_entry = {
                'rate': rate,
                'min_deposit': min_deposit or 10000,
                'note': '電子渠道新資金',
                'source': 'hket',
                'conditions': ['new_funds', 'electronic_channel']
            }
        elif current_condition == 'new_customer':
            rate_entry = {
                'rate': rate,
                'min_deposit': min_deposit or 10000,
                'note': '新客戶專享',
                'source': 'hket',
                'conditions': ['new_customer']
            }
        else:
            rate_entry = {
                'rate': rate,
                'min_deposit': min_deposit or 10000,
                'note': '定期存款',
                'source': 'hket',
                'conditions': ['new_funds', 'electronic_channel']
            }
        
        # Store rate - for same period, prefer new_funds over exchange
        if period_key not in hkd:
            hkd[period_key] = rate_entry
        elif current_condition == 'new_funds':
            # Replace exchange rate with new_funds rate for same period
            hkd[period_key] = rate_entry
    
    if hkd:
        rates['hkd'] = hkd
    
    # Try to extract USD rates if present
    usd_section = text.find('美元')
    if usd_section >= 0:
        usd_text = text[usd_section:usd_section+1000]
        usd = _parse_currency_section(usd_text, 'usd')
        if usd:
            rates['usd'] = usd
    
    # Try to extract CNY rates if present
    cny_section = text.find('人民幣')
    if cny_section >= 0:
        cny_text = text[cny_section:cny_section+1000]
        cny = _parse_currency_section(cny_text, 'cny')
        if cny:
            rates['cny'] = cny
    
    if rates:
        return rates
    return None


def _parse_currency_section(text, currency):
    """Parse USD or CNY rate section."""
    rates = {}
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        period_match = re.search(r'(\d+)\s*(個月|星期)', line)
        if not period_match:
            continue
        
        period_num = int(period_match.group(1))
        period_unit = period_match.group(2)
        
        if period_unit in ['星期', '周']:
            period_key = f'{period_num}w'
        else:
            period_key = f'{period_num}m'
        
        rate_match = re.search(r'(\d+\.?\d*)厘', line)
        if rate_match:
            rate = float(rate_match.group(1))
            rates[period_key] = {
                'rate': rate,
                'min_deposit': 10000,
                'note': f'南洋商業銀行{currency.upper()}定期存款',
                'source': 'hket'
            }
    
    return rates if rates else None