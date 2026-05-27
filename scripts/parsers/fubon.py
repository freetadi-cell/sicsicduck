"""富邦銀行 Fubon Bank - Parser for time deposit rates.

Page: https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html

Three sections:
1. 新資金定期存款優惠 (new funds): HKD/USD 3m only
2. Fubon+ 港元 (any funds): take highest tier
3. Fubon+ 美元 (any funds): take highest tier

For 3m: both rates exist. New funds (2.8%/3.9%) stored as primary,
Fubon+ rate (2.65%/3.8%) stored as any_funds_rate for 不限資金 filter.
"""
import re


def parse(text, tables=None):
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

        hkd_m = re.search(r'港元\s+(\d+\.\d+)%', nf_section)
        usd_m = re.search(r'美元\s+(\d+\.\d+)%', nf_section)

        if hkd_m:
            hkd['3m'] = {'rate': float(hkd_m.group(1)), 'new_funds': True}
        if usd_m:
            usd['3m'] = {'rate': float(usd_m.group(1)), 'new_funds': True}

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
        result['note'] = '新資金/Fubon+手機App定存利率（取最高）'
        return result
    return None


def _extract_tier_rates(section, rates, currency):
    """Extract the highest tier rates from a Fubon+ section.

    If a period already has a new_funds rate, store the any-funds rate
    as any_funds_rate instead of overwriting.
    """
    tier_labels = re.split(r'(?:港元|美元)[\d,]+\s*(?:至[\d,]+\w*)?(?:\s*或?\s*以上)?', section)

    if len(tier_labels) < 2:
        return

    last_tier = tier_labels[-1]
    pcts = re.findall(r'(\d+\.\d+)%', last_tier)

    if not pcts:
        if len(tier_labels) >= 3:
            last_tier = tier_labels[-2]
            pcts = re.findall(r'(\d+\.\d+)%', last_tier)

    if not pcts:
        return

    periods = ['1m', '2m', '3m', '4m', '6m', '12m']
    for i, pct in enumerate(pcts):
        if i < len(periods):
            val = float(pct)
            key = periods[i]
            existing = rates.get(key)

            if existing is None:
                # No rate yet, set as any-funds rate
                rates[key] = {'rate': val, 'new_funds': False}
            elif existing.get('new_funds') is True and existing.get('rate', 0) > val:
                # Already has a higher new-funds rate, store this as any_funds_rate
                existing['any_funds_rate'] = val
            elif val > existing.get('rate', 0):
                # This rate is higher, replace
                rates[key] = {'rate': val, 'new_funds': False}
