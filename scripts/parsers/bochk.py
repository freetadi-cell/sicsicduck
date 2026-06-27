"""中銀香港 BOCHK - Parser for time deposit promotion rates."""
import re

def parse(text, tables=None, html=None):
    """Parse BOCHK new fund time deposit rates.
    
    Page has:
    1. 新資金特優定期存款 - HKD/USD/RMB for 3m, 6m, 7m, 12m
    2. 特優人民幣及外幣定期存款優惠 - 兌換 rates for 7d, 1m
    3. 牌價利率 - https://www.bochk.com/whk/rates/depositRates/depositRates-input.action?lang=hk
    """
    if not text:
        return None
    
    rates = {}
    note = '網上銀行新資金特優定期存款'
    
    # Check if this is card rate page
    is_card_rate = '港元定期存款利率表' in text or '牌價' in text or '存款利率表' in text
    
    if is_card_rate:
        # Parse card rate (existing_funds) - 牌價利率
        rates['hkd'] = {}
        rates['usd'] = {}
        
        # Snapshot format: row "1 個月 0.10000% 0.10000% 0.10000%"
        periods = {
            '1w': '7 天', '2w': '14 天',
            '1m': '1 個月', '2m': '2 個月', '3m': '3 個月', '6m': '6 個月',
            '9m': '9 個月', '12m': '12 個月'
        }
        
        for period, label in periods.items():
            # Try snapshot format: row "1 個月 0.10000% 0.10000% 0.10000%"
            m = re.search(rf'row "{label}\s+(\d+\.\d+)%', text)
            if m:
                rate = float(m.group(1))
                rates['hkd'][period] = {
                    'new_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'existing_funds': {'rate': rate, 'min_deposit': 10000, 'note': '定期存款牌價利率', 'source': 'bank'},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
            # Try text format: 1 個月 0.10000%
            elif f'{label}' in text:
                m = re.search(rf'{label}\s+(\d+\.\d+)%', text)
                if m:
                    rate = float(m.group(1))
                    rates['hkd'][period] = {
                        'new_funds': {'rate': None, 'min_deposit': None, 'note': None},
                        'existing_funds': {'rate': rate, 'min_deposit': 10000, 'note': '定期存款牌價利率', 'source': 'bank'},
                        'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                    }
        
        if rates.get('hkd'):
            rates['note'] = '定期存款牌價利率'
            rates['_use_new_structure'] = True
            return rates
    
    # Find the rate table section (new funds promotion)
    table_idx = text.find('3 個月\t6 個月\t12 個月')
    if table_idx < 0:
        table_idx = text.find('3 个 月\t6 个 月\t12 个 月')
    if table_idx < 0:
        table_idx = text.find('定期存款期')
    
    if table_idx < 0:
        return None
    
    section = text[table_idx:table_idx+2000]
    
    # Extract HKD rates (first row after 港元) - new_funds
    hkd_match = re.search(r'港元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if hkd_match:
        rates['hkd'] = {
            '3m': {'rate': float(hkd_match.group(1)), 'fund_type': 'new_funds', 'min_deposit': 10000},
            '6m': {'rate': float(hkd_match.group(2)), 'fund_type': 'new_funds', 'min_deposit': 10000}
        }
        hkd_12 = re.search(r'港元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if hkd_12:
            rates['hkd']['12m'] = {'rate': float(hkd_12.group(3)), 'fund_type': 'new_funds', 'min_deposit': 10000}
    
    # USD rates - new_funds
    usd_match = re.search(r'美元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if usd_match:
        rates['usd'] = {
            '3m': {'rate': float(usd_match.group(1)), 'fund_type': 'new_funds', 'min_deposit': 1000},
            '6m': {'rate': float(usd_match.group(2)), 'fund_type': 'new_funds', 'min_deposit': 1000}
        }
        usd_12 = re.search(r'美元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if usd_12:
            rates['usd']['12m'] = {'rate': float(usd_12.group(3)), 'fund_type': 'new_funds', 'min_deposit': 1000}
    
    # CNY (人民幣) rates - new_funds
    cny_match = re.search(r'人民幣\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if cny_match:
        rates['cny'] = {
            '3m': {'rate': float(cny_match.group(1)), 'fund_type': 'new_funds', 'min_deposit': 10000},
            '6m': {'rate': float(cny_match.group(2)), 'fund_type': 'new_funds', 'min_deposit': 10000}
        }
        cny_12 = re.search(r'人民幣\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+\S+\s+(\d+\.\d+)%', section)
        if cny_12:
            rates['cny']['12m'] = {'rate': float(cny_12.group(3)), 'fund_type': 'new_funds', 'min_deposit': 10000}
    
    # CNY exchange (兌換) rates
    # Section: 特優人民幣及外幣定期存款優惠
    exchange_idx = text.find('特優人民幣及外幣定期存款')
    if exchange_idx >= 0:
        exchange_section = text[exchange_idx:exchange_idx+1500]
        # 7天/1個月 兌換 table: 人民幣 column with 7天 and 1個月 rows
        # Format: 7天 ... 11.8% ... ; 1個月 ... 3.5% ...
        # Try to find CNY exchange rates
        cny_7d = re.search(r'7天.*?人民幣.*?(\d+\.\d+)%', exchange_section, re.DOTALL)
        if not cny_7d:
            # Alternative: find the row for 7天 then get 人民幣 column
            row_7d = re.search(r'7天\s+(?:[\d.]+%\s+)*?(\d+\.\d+)%\s+(?:[\d.]+%\s+)*', exchange_section)
            if row_7d:
                # Check if 人民幣 is in context
                pass
        
        # Better approach: find the table with rows 7天 and 1個月
        # The table has columns for 澳元 紐元 英鎊 加元 人民幣 美元 歐羅
        # Find column positions
        header_match = re.search(r'澳元\s*紐元\s*英鎊\s*加元\s*人民幣\s*美元\s*歐羅', exchange_section)
        if header_match:
            # Find 7天 row - exchange condition
            row_7d = re.search(r'7天\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%', exchange_section)
            if row_7d:
                # Column 5 is 人民幣
                cny_7d_rate = float(row_7d.group(5))
                if 'cny' not in rates:
                    rates['cny'] = {}
                rates['cny']['1w'] = {'rate': cny_7d_rate, 'conditions': ['exchange'], 'min_deposit': 10000}
            
            # Find 1個月 row - exchange condition
            row_1m = re.search(r'1個月\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%', exchange_section)
            if row_1m:
                cny_1m_rate = float(row_1m.group(5))
                if 'cny' not in rates:
                    rates['cny'] = {}
                rates['cny']['1m'] = {'rate': cny_1m_rate, 'conditions': ['exchange'], 'min_deposit': 10000}
    
    if rates:
        rates['note'] = note
        return rates
    return None
