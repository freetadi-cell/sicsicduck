"""恒生銀行 Hang Seng Bank - Parser for new fund deposit rates."""
import re

def parse(text, tables=None):
    """Parse Hang Seng new fund time deposit rates.
    
    URL: https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html
    Page format:
    港元定期存款特優年利率 (%)
    存款期  網上理財  分行/電話理財
    3個月  2.20  2.20
    6個月  2.00  2.00
    """
    if not text:
        return None
    
    rates = {}
    note = '新資金定期存款優惠（網上理財）'
    
    # Find HKD section
    hkd_idx = text.find('港元定期存款特優年利率')
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx+500]
        hkd_rates = {}
        for period, label in [('3m', '3個月'), ('6m', '6個月')]:
            # Pattern: 3個月  2.20  2.20 (no % sign)
            m = re.search(rf'{label}\s+(\d+\.\d+)\s+(\d+\.\d+)', hkd_section)
            if m:
                hkd_rates[period] = float(m.group(1))  # 網上理財 rate
        if hkd_rates:
            rates['hkd'] = hkd_rates
    
    # Find USD section
    usd_idx = text.find('美元定期存款特優年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+500]
        usd_rates = {}
        for period, label in [('3m', '3個月'), ('6m', '6個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)\s+(\d+\.\d+)', usd_section)
            if m:
                usd_rates[period] = float(m.group(1))
        if usd_rates:
            rates['usd'] = usd_rates
    
    if rates:
        rates['note'] = note
        return rates
    
    # Fallback: board rates
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
