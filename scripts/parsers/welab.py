"""匯立銀行 WeLab Bank - Parser for GoSave 2.0 time deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse WeLab Bank GoSave 2.0 rates.
    
    Page shows currency tabs: HKD, USD, CNY, AUD, GBP
    Default visible tab is HKD.
    Only parse what's clearly on the page (HKD by default).
    """
    if not text:
        return None
    
    rates = {}
    note = 'GoSave 2.0 定期存款'
    
    # HKD rates - look for the rate table
    hkd_rates = {}
    for period, label in [('1m', '1-month'), ('3m', '3-month'), ('6m', '6-month'), ('12m', '12-month')]:
        pattern = rf'{label}\s+(\d+\.\d+)%'
        m = re.search(pattern, text)
        if m:
            hkd_rates[period] = float(m.group(1))
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    # USD: WeLab shows rates in tabs, USD tab is not visible by default
    # Only parse if there's a clear USD rate section (different from HKD)
    # We skip USD for now as it requires clicking the tab
    
    if rates:
        rates['note'] = note
        return rates
    return None
