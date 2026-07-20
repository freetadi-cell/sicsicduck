"""渣打銀行 Standard Chartered - Parser for online time deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse SC HK online time deposit rates.
    
    Page format:
    1. Tables with format: 新資金達港元10,000或以上 | 貨幣 | 存款期 | 特惠定期存款年利率
       港元 | 3個月 | 2.40%
       港元 | 6個月 | 2.40%
       港元 | 12個月 | 2.80%
    2. USD Time Deposit: 3 months 3.20%, 6 months 3.30%, 12 months 2.70%
    3. RMB Time Deposit: 3 months X.XX%, 6 months X.XX%, 12 months X.XX%
    4. 牌價利率: https://www.sc.com/hk/deposits/board-rates/
    """
    if not text:
        return None
    
    rates = {}
    note = '網上新資金定期存款特惠年利率'
    
    # Check if this is card rate page (Board Rates)
    is_card_rate = 'Board Rates' in text or '牌價' in text or 'Time Deposit Rates' in text and 'Deposit period' in text
    
    if is_card_rate:
        # Parse card rate (existing_funds) - 牌價利率
        rates['hkd'] = {}
        rates['usd'] = {}
        
        # Snapshot/text format: "7 days 0.100%" or "1 month 0.100%"
        periods = {
            '1w': '7 days', '2w': '14 days',
            '1m': '1 month', '2m': '2 months', '3m': '3 months', '6m': '6 months',
            '9m': '9 months', '12m': '12 months'
        }
        
        for period, label in periods.items():
            # Try snapshot format: row "7 days 0.100% 0.100% 0.100%"
            m = re.search(rf'row "{label}\s+(\d+\.\d+)%', text)
            if m:
                rate = float(m.group(1))
                rates['hkd'][period] = {
                    'new_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'existing_funds': {'rate': rate, 'min_deposit': 10000, 'note': '定期存款牌價利率', 'source': 'bank'},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
            # Try text format: 7 days 0.100%
            elif label in text:
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
    
    # Try parsing tables first (format from requests + BeautifulSoup)
    if tables:
        for table in tables:
            # Check for new funds table format
            if '新資金達' in table or '特惠定期存款年利率' in table:
                lines = table.split('\n')
                current_currency = None
                for line in lines:
                    # Detect currency
                    if '港元' in line and 'HKD' not in line.upper():
                        current_currency = 'hkd'
                    elif '美元' in line or 'USD' in line:
                        current_currency = 'usd'
                    elif '人民幣' in line or 'RMB' in line or 'CNY' in line:
                        current_currency = 'cny'
                    
                    # Extract rates: format "3個月 | 2.40%" or "12個月 | 2.80%"
                    m = re.search(r'(\d+)個月\s*\|?\s*(\d+\.\d+)%', line)
                    if m and current_currency:
                        months = int(m.group(1))
                        rate = float(m.group(2))
                        period_key = f'{months}m' if months <= 12 else '12m'
                        
                        if current_currency not in rates:
                            rates[current_currency] = {}
                        rates[current_currency][period_key] = rate
    
    # Fallback to text parsing
    if not rates:
        # HKD section (new funds)
        hkd_idx = text.find('HKD Time Deposit')
        usd_idx = text.find('USD Time Deposit')
        rmb_idx = text.find('RMB Time Deposit')
        
        if hkd_idx >= 0:
            end = usd_idx if usd_idx > hkd_idx else rmb_idx if rmb_idx > hkd_idx else hkd_idx + 500
            section = text[hkd_idx:end]
            hkd_rates = {}
            for period, label in [('3m', '3 months'), ('6m', '6 months'), ('12m', '12 months')]:
                pattern = rf'{label}\s+(\d+\.\d+)%'
                m = re.search(pattern, section)
                if m:
                    hkd_rates[period] = float(m.group(1))
            if hkd_rates:
                rates['hkd'] = hkd_rates
        
        # USD section
        if usd_idx >= 0:
            end = rmb_idx if rmb_idx > usd_idx else usd_idx + 500
            section = text[usd_idx:end]
            usd_rates = {}
            for period, label in [('3m', '3 months'), ('6m', '6 months'), ('12m', '12 months')]:
                pattern = rf'{label}\s+(\d+\.\d+)%'
                m = re.search(pattern, section)
                if m:
                    usd_rates[period] = float(m.group(1))
            if usd_rates:
                rates['usd'] = usd_rates
        
        # CNY / RMB section
        if rmb_idx >= 0:
            section = text[rmb_idx:rmb_idx+500]
            cny_rates = {}
            for period, label in [('3m', '3 months'), ('6m', '6 months'), ('12m', '12 months')]:
                pattern = rf'{label}\s+(\d+\.\d+)%'
                m = re.search(pattern, section)
                if m:
                    cny_rates[period] = float(m.group(1))
            if cny_rates:
                rates['cny'] = cny_rates
    
    if rates:
        rates['note'] = note
        return rates
    return None
