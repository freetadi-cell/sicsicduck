"""富邦銀行 Fubon Bank - Parser for time deposit rates.

Page: https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html

Three sections:
1. 新資金定期存款優惠 (HKD 500K+/USD 128K+): 3/6/12m
2. Fubon+ 港元 (any funds): take highest tier (500K+)
3. Fubon+ 美元 (any funds): take highest tier (65K+)
"""
import re


def parse(text, tables=None, html=None):
    """Parse Fubon Bank time deposit rates."""
    if not text:
        return None

    hkd = {}
    usd = {}

    # === Section 1: 新資金定期存款優惠 ===
    nf_idx = text.find('新資金定期存款優惠')
    if nf_idx >= 0:
        nf_end = text.find('手機應用程式限定', nf_idx + 10)
        nf_section = text[nf_idx:nf_end if nf_end > 0 else nf_idx + 2000]

        # Format in markdown:
        # 存款期 三個月 六個月 九個月 十二個月
        # 港元 2.95% 3.1% 3.1% 3.1%
        # 美元 4.1% / / /
        
        hkd_rates = _extract_nf_row(nf_section, '港元')
        usd_rates = _extract_nf_row(nf_section, '美元')

        for period, rate in hkd_rates.items():
            hkd[period] = {
                'rate': rate,
                'fund_type': 'new_funds',
                'min_deposit': 500000,
                'note': '新資金定期存款優惠',
                'source': 'bank'
            }
        for period, rate in usd_rates.items():
            usd[period] = {
                'rate': rate,
                'fund_type': 'new_funds',
                'min_deposit': 128000,
                'note': '新資金定期存款優惠',
                'source': 'bank'
            }

    # === Section 2: Fubon+ 港元 ===
    hkd_idx = text.find('特優港元定期存款優惠')
    if hkd_idx >= 0:
        hkd_end = text.find('特優美元定期存款優惠', hkd_idx)
        hkd_section = text[hkd_idx:hkd_end if hkd_end > 0 else hkd_idx + 3000]
        _extract_tier_rates(hkd_section, hkd, '港元')

    # === Section 3: Fubon+ 美元 ===
    usd_idx = text.find('特優美元定期存款優惠')
    if usd_idx >= 0:
        usd_end = text.find('特優外幣定期存款優惠', usd_idx)
        usd_section = text[usd_idx:usd_end if usd_end > 0 else usd_idx + 3000]
        _extract_tier_rates(usd_section, usd, '美元')

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd

    if result:
        return result
    return None


def _extract_nf_row(section, currency):
    """Extract new fund rates for a currency from the new fund section.

    Format in markdown:
    存款期 三個月 六個月 九個月 十二個月
    港元 2.95% 3.1% 3.1% 3.1%
    美元 4.1% / / /
    """
    rates = {}
    
    # Find the currency line
    # Pattern: 港元 followed by 4 percentages (some may be /)
    pattern = rf'{re.escape(currency)}\s+([\d.]+%|/)\s+([\d.]+%|/)\s+([\d.]+%|/)\s+([\d.]+%|/)'
    m = re.search(pattern, section)
    
    if m:
        # Extract valid percentages
        periods = ['3m', '6m', '9m', '12m']
        for i, period in enumerate(periods):
            val = m.group(i + 1)
            if val != '/':
                # Remove % and convert to float
                rate = float(val.replace('%', ''))
                rates[period] = rate
    
    return rates


def _extract_tier_rates(section, rates, currency):
    """Extract the highest tier rates from a Fubon+ section.
    
    Format in markdown:
    存款期/存款金額 一個月 兩個月 三個月 四個月 六個月 十二個月
    港元500,000 或以上 2.45% 2.55% 2.9% 2.9% 3.05% 3.05%
    """
    # Find lines with currency and rates
    lines = section.split('\n')
    
    for line in lines:
        # Look for lines starting with currency and containing rates
        if not (line.strip().startswith(currency) or line.strip().startswith('港元') or line.strip().startswith('美元')):
            continue
        
        # Extract all percentages from this line
        pcts = re.findall(r'(\d+\.\d+)%', line)
        
        if len(pcts) >= 6:
            # Periods: 1m, 2m, 3m, 4m, 6m, 12m
            periods = ['1m', '2m', '3m', '4m', '6m', '12m']
            min_deposit = 500000 if currency == '港元' else 65000
            
            for i, pct in enumerate(pcts[:6]):
                val = float(pct)
                key = periods[i]
                
                # Only update if this is a better rate or doesn't exist
                existing = rates.get(key)
                if existing is None:
                    rates[key] = {
                        'rate': val,
                        'fund_type': 'existing_funds',
                        'min_deposit': min_deposit,
                        'note': 'Fubon+手機App定期存款',
                        'source': 'bank'
                    }
                elif existing.get('fund_type') == 'new_funds' and existing.get('rate', 0) > val:
                    # Keep new_funds rate but note existing_funds rate
                    existing['existing_funds_rate'] = val
                elif val > existing.get('rate', 0):
                    rates[key] = {
                        'rate': val,
                        'fund_type': 'existing_funds',
                        'min_deposit': min_deposit,
                        'note': 'Fubon+手機App定期存款',
                        'source': 'bank'
                    }
            break