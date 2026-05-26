"""恒生銀行 Hang Seng Bank - Parser for new fund deposit rates."""
import re

def parse(text, tables=None):
    """Parse Hang Seng new fund time deposit rates.
    
    URL: https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html
    Page has new fund promo rates for HKD/USD/RMB.
    """
    if not text:
        return None
    
    rates = {}
    note = '新資金定期存款優惠'
    
    # Look for percentage rates - page shows rates like 2.2%, 3.x% etc
    # Find all rates in the page
    pcts = re.findall(r'高達\s*(\d+\.\d+)%', text)
    if pcts:
        # Typically: HKD rate, USD rate, RMB rate
        hkd_rate = max(float(x) for x in pcts) if pcts else None
        if hkd_rate:
            rates['hkd'] = {'3m': hkd_rate}
    
    # Alternative: look for specific patterns
    # Pattern: 年利率 X.XX%
    if 'hkd' not in rates:
        rate_matches = re.findall(r'(\d+\.\d+)%\s*(?:年利率|p\.a\.)', text)
        if not rate_matches:
            rate_matches = re.findall(r'年利率.*?(\d+\.\d+)%', text)
        if rate_matches:
            rates['hkd'] = {'3m': max(float(x) for x in rate_matches)}
    
    if rates:
        rates['note'] = note
        return rates
    
    # Fallback: board rates from main page
    board_idx = text.find('牌價')
    if board_idx >= 0:
        section = text[board_idx:board_idx+1500]
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            pattern = rf'{label}\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%'
            m = re.search(pattern, section)
            if m:
                hkd_rates[period] = float(m.group(4))
        if hkd_rates:
            rates['hkd'] = hkd_rates
            rates['note'] = '定期存款牌價利率'
            return rates
    
    return None
