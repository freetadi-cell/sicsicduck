"""滙豐銀行 HSBC - Parser for deposit rates from text content.

Extracts:
- RewardCash Time Deposit (new funds via mobile app): HKD/USD 3m/6m
- Preferential New Fund Time Deposit: HKD 3m/6m, USD 3m/6m/12m, CNY 3m/6m/12m
- Exchange rate promo (HKD/USD 1w via currency exchange)

All rates are tagged with fund_type='new_funds' or conditions=['exchange']
"""
import re

def parse(text, tables=None, html=None):
    """Parse HSBC HK deposit rates.
    
    Page structure:
    1. RewardCash Time Deposit (新資金手機App優惠)
    2. Preferential New Fund Time Deposit Rates (新資金定期優惠)
    3. Exchange rate promo (兌換資金優惠)
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
    
    # Preferential HKD
    hkd_pref = {}
    hkd_pref_match = re.search(
        r'Preferential.*?HKD.*?Minimum deposit.*?((?:\d+ months?\s+\d+\.\d+%\s*)+)',
        pref_text, re.DOTALL | re.IGNORECASE
    )
    if hkd_pref_match:
        block = hkd_pref_match.group(1)
        for period, label in [('3m', '3 months'), ('6m', '6 months')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', block)
            if m:
                hkd_pref[period] = float(m.group(1))
    
    # === Preferential New Fund CNY ===
    cny_pref = {}
    cny_pref_match = re.search(
        r'Preferential.*?RMB.*?Minimum deposit.*?((?:\d+ months?\s+\d+\.\d+%\s*)+)',
        pref_text, re.DOTALL | re.IGNORECASE
    )
    if cny_pref_match:
        block = cny_pref_match.group(1)
        for period, label in [('3m', '3 months'), ('6m', '6 months'), ('12m', '12 months')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', block)
            if m:
                cny_pref[period] = float(m.group(1))
    
    # === Exchange rate promo (1 week rates via currency exchange) ===
    hkd_exchange = {}
    usd_exchange = {}
    cny_exchange = {}
    
    # Look for exchange/currency conversion promos
    exchange_section = text.find('Currency exchange') if 'Currency exchange' in text else text.find('兌換')
    if exchange_section > 0:
        exchange_text = text[exchange_section:exchange_section + 2000]
        # HKD exchange: look for 1 week rates
        hkdx_match = re.search(r'HKD.*?(?:1\s*星期|7\s*天).*?(\d+\.\d+)%', exchange_text)
        if hkdx_match:
            hkd_exchange['1w'] = float(hkdx_match.group(1))
        # USD exchange
        usdx_match = re.search(r'USD.*?(?:1\s*星期|7\s*天).*?(\d+\.\d+)%', exchange_text)
        if usdx_match:
            usd_exchange['1w'] = float(usdx_match.group(1))
        # CNY exchange
        cnyx_match = re.search(r'(?:RMB|CNY|人民幣).*?(?:1\s*星期|7\s*天).*?(\d+\.\d+)%', exchange_text)
        if cnyx_match:
            cny_exchange['1w'] = float(cnyx_match.group(1))
    
    # Build result with fund_type and conditions
    result = {}
    
    # HKD: RewardCash (new_funds) + Preferential (new_funds) + Exchange (exchange)
    hkd_final = {}
    # RewardCash rates are new_funds
    for p in ['3m', '6m']:
        if p in hkd_rc:
            hkd_final[p] = {'rate': hkd_rc[p], 'fund_type': 'new_funds', 'min_deposit': 10000}
    # Preferential HKD rates are new_funds
    for p in ['3m', '6m']:
        if p in hkd_pref:
            hkd_final[p] = {'rate': hkd_pref[p], 'fund_type': 'new_funds', 'min_deposit': 10000}
    # Exchange rates
    for p in ['1w']:
        if p in hkd_exchange:
            hkd_final[p] = {'rate': hkd_exchange[p], 'conditions': ['exchange'], 'min_deposit': 10000}
    if hkd_final:
        result['hkd'] = hkd_final
    
    # USD: RewardCash (new_funds) + Preferential (new_funds) + Exchange (exchange)
    usd_final = {}
    for p in ['3m', '6m']:
        if p in usd_rc:
            usd_final[p] = {'rate': usd_rc[p], 'fund_type': 'new_funds', 'min_deposit': 2000}
    for p in ['3m', '6m', '12m']:
        if p in usd_pref:
            usd_final[p] = {'rate': usd_pref[p], 'fund_type': 'new_funds', 'min_deposit': 2000}
    for p in ['1w']:
        if p in usd_exchange:
            usd_final[p] = {'rate': usd_exchange[p], 'conditions': ['exchange'], 'min_deposit': 2000}
    if usd_final:
        result['usd'] = usd_final
    
    # CNY: Preferential (new_funds) + Exchange (exchange)
    cny_final = {}
    for p in ['3m', '6m', '12m']:
        if p in cny_pref:
            cny_final[p] = {'rate': cny_pref[p], 'fund_type': 'new_funds', 'min_deposit': 10000}
    for p in ['1w']:
        if p in cny_exchange:
            cny_final[p] = {'rate': cny_exchange[p], 'conditions': ['exchange'], 'min_deposit': 10000}
    if cny_final:
        result['cny'] = cny_final
    
    if result:
        result['note'] = '滙豐定期存款優惠（新資金）'
        return result
    
    # Fallback: try to find CNY exchange rates on the page
    if text:
        cny_rates = {}
        # Look for RMB/CNY exchange promo: "7天" or "1星期" with high rates
        for m in re.finditer(r'(?:人民幣|RMB|CNY).*?(\d+)\s*(?:天|星期).*?(\d+\.?\d*)\s*%', text):
            days = int(m.group(1))
            if days == 7:
                cny_rates['1w'] = {'rate': float(m.group(2)), 'conditions': ['exchange']}
        for m in re.finditer(r'(?:人民幣|RMB|CNY).*?(\d+)\s*個月.*?(\d+\.?\d*)\s*%', text):
            n = int(m.group(1))
            pk = f'{n}m' if f'{n}m' in ['1m', '2m', '3m', '6m', '12m'] else None
            if pk:
                cny_rates[pk] = {'rate': float(m.group(2))}
        if cny_rates:
            result = {'cny': cny_rates, 'note': '滙豐人民幣定期存款'}
            return result
    
    return None
