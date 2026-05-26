"""中信銀行（國際）CNCBI - Parser for inMotion time deposit promo rates."""
import re

def parse(text, tables=None):
    """Parse CNCBI inMotion new fund time deposit promo rates.
    
    URL: https://www.cncbinternational.com/personal/e-banking/inmotion/tc/offers/time_deposit/index.html
    Page shows: 高達 2.68% (HKD), 高達 3.62% (USD), 高達 1.35% (RMB)
    """
    if not text:
        return None
    
    rates = {}
    note = 'inMotion新資金定期存款特惠年利率'
    
    # Find all "高達 X.XX%" patterns
    pcts = re.findall(r'高達\s*(\d+\.\d+)%', text)
    
    if len(pcts) >= 1:
        # First is typically HKD, second USD, third RMB
        rates['hkd'] = {'3m': float(pcts[0])}
        if len(pcts) >= 2:
            rates['usd'] = {'3m': float(pcts[1])}
    
    if not rates:
        # Fallback: look for any rate percentages on the page
        all_pcts = re.findall(r'(\d+\.\d+)%', text)
        if all_pcts:
            # Filter for reasonable deposit rates (>0.5%)
            valid = [float(x) for x in all_pcts if float(x) > 0.5]
            if valid:
                rates['hkd'] = {'3m': max(valid)}
    
    # Last fallback: board rates from rate table page
    if not rates:
        board_idx = text.find('定期存款利率')
        if board_idx >= 0:
            section = text[board_idx:board_idx+2000]
            hkd_rates = {}
            for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
                m = re.search(rf'{label}\s+(\d+\.\d+)%', section)
                if m:
                    hkd_rates[period] = float(m.group(1))
            if hkd_rates:
                rates['hkd'] = hkd_rates
                note = '定期存款利率'
    
    if rates:
        rates['note'] = note
        return rates
    return None
