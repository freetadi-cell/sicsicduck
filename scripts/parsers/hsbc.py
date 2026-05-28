"""滙豐銀行 HSBC - Parser for deposit rates from text content."""
import re

def parse(text, tables=None):
    """Parse HSBC HK deposit rates.
    
    Page has two main sections:
    1. RewardCash Time Deposit (HKD + USD) - 3m, 6m only
    2. Preferential New Fund Time Deposit Rates (HKD + USD) - 3m, 6m, 12m
    
    We capture RewardCash rates for HKD (3m/6m) and USD (3m/6m),
    and Preferential USD 12m since it's the only 12m rate available.
    """
    rates = {}
    
    if not text:
        return None
    
    # === RewardCash section ===
    rc_end = text.find('Preferential New Fund')
    rc_text = text[:rc_end] if rc_end > 0 else text
    
    hkd_rc = {}
    usd_rc = {}
    
    # Find HKD RewardCash rates
    hkd_match = re.search(r'HKD.*?Equivalent interest rate.*?((?:\d+ months?\s+\d+\.\d+%\s*)+)', rc_text, re.DOTALL)
    if hkd_match:
        block = hkd_match.group(1)
        for period, label in [('3m', '3 months'), ('6m', '6 months')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', block)
            if m:
                hkd_rc[period] = float(m.group(1))
    
    # Find USD RewardCash rates
    usd_match = re.search(r'USD.*?Equivalent interest rate.*?((?:\d+ months?\s+\d+\.\d+%\s*)+)', rc_text, re.DOTALL)
    if usd_match:
        block = usd_match.group(1)
        for period, label in [('3m', '3 months'), ('6m', '6 months')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', block)
            if m:
                usd_rc[period] = float(m.group(1))
    
    # === Preferential New Fund section ===
    pref_text = text[rc_end:] if rc_end > 0 else ''
    
    # Preferential USD
    usd_pref = {}
    usd_pref_match = re.search(
        r'Preferential USD.*?online offer.*?Minimum deposit.*?((?:\d+ months?\s+\d+\.\d+%\s*)+)',
        pref_text, re.DOTALL | re.IGNORECASE
    )
    if usd_pref_match:
        block = usd_pref_match.group(1)
        for period, label in [('3m', '3 months'), ('6m', '6 months'), ('12m', '12 months')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', block)
            if m:
                usd_pref[period] = float(m.group(1))
    
    # Build result
    result = {}
    
    # HKD: RewardCash 3m/6m only
    if hkd_rc:
        result['hkd'] = hkd_rc
    
    # USD: RewardCash 3m/6m + Preferential 12m
    if usd_rc or usd_pref:
        usd_final = {}
        for p in ['3m', '6m']:
            if p in usd_rc:
                usd_final[p] = usd_rc[p]
        if '12m' in usd_pref:
            usd_final['12m'] = usd_pref['12m']
        if usd_final:
            result['usd'] = usd_final
    
    # Use note 'RewardCash定存' as default; USD 12m will get different note
    if result:
        result['note'] = 'RewardCash定存（手機App新資金）'
        # If USD has 12m from Preferential, store separate note
        if 'usd' in result and '12m' in result.get('usd', {}):
            result['usd_note'] = '新資金定期存款優惠'
        return result
    return None
