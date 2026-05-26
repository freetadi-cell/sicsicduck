"""恒生銀行 Hang Seng Bank - Parser for deposit rates."""
import re

def parse(text, tables=None):
    """Parse Hang Seng deposit rates.
    
    Page shows 牌價 table:
    存款期  10,000-99,999  100,000-499,999  500,000-999,999  1,000,000+
    一個月  0.1000%  0.1000%  0.1000%  0.1000%
    三個月  0.1250%  ...
    """
    if not text:
        return None
    
    rates = {}
    note = '定期存款牌價利率'
    
    # Find 牌價 section
    board_idx = text.find('港元定期存款利率\n牌價')
    if board_idx < 0:
        board_idx = text.find('牌價')
    if board_idx < 0:
        return None
    
    section = text[board_idx:board_idx+1500]
    
    # Take highest tier (1,000,000或以上 = 4th column)
    hkd_rates = {}
    for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
        pattern = rf'{label}\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%'
        m = re.search(pattern, section)
        if m:
            hkd_rates[period] = float(m.group(4))  # highest tier
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    # USD - page may show USD tab separately; check for USD section
    # Hang Seng page shows HKD by default; USD requires tab click
    # We skip USD for now unless clearly visible
    
    if rates:
        rates['note'] = note
        return rates
    return None
