"""渣打銀行 Standard Chartered - Parser for online time deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse SC HK online time deposit rates.
    
    Page format:
    HKD Time Deposit: 3 months 2.30%, 6 months 2.10%, 12 months 2.00%
    USD Time Deposit: 3 months 3.20%, 6 months 3.30%, 12 months 2.70%
    RMB Time Deposit: 3 months X.XX%, 6 months X.XX%, 12 months X.XX%
    """
    if not text:
        return None
    
    rates = {}
    note = '網上新資金定期存款特惠年利率'
    
    # HKD section
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
