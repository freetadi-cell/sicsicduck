"""滙豐銀行 HSBC - Parser for deposit rates from text content."""
import re

def parse(text, tables=None):
    """Parse HSBC HK deposit rates.
    
    Page has RewardCash Time Deposit rates.
    Look for the rate table pattern:
    Tenor  Equivalent interest rate (p.a.)
    3 months  2.435%
    6 months  2.215%
    
    HKD and USD sections each have their own table.
    """
    rates = {}
    note = 'RewardCash定存（手機App新資金）'
    
    if not text:
        return None
    
    # Find all "Equivalent interest rate" tables
    # Pattern: "3 months  2.435%"
    # Each currency section has its own rate table
    
    # Split by currency headers
    # Find HKD section: look for "HKD" followed by rate data, then "USD" starts next section
    sections = re.split(r'\bUSD\b', text)
    
    # First section (before first "USD") should have HKD rates
    hkd_text = sections[0] if sections else ''
    
    # Look for rates in format: "3 months  2.435%"
    hkd_rates = {}
    for period, label in [('3m', '3 months'), ('6m', '6 months')]:
        pattern = rf'{label}\s+(\d+\.\d+)%'
        m = re.search(pattern, hkd_text)
        if m:
            hkd_rates[period] = float(m.group(1))
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    # USD section: everything after first "USD"
    if len(sections) > 1:
        usd_text = 'USD' + sections[1]
        usd_rates = {}
        for period, label in [('3m', '3 months'), ('6m', '6 months')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, usd_text)
            if m:
                usd_rates[period] = float(m.group(1))
        if usd_rates:
            rates['usd'] = usd_rates
    
    if rates:
        rates['note'] = note
        return rates
    return None
