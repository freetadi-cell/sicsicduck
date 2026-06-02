"""富邦銀行 Fubon Bank - Parser for time deposit rates.

Page: https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html

Three sections:
1. 新資金定期存款優惠 (HKD 500K+/USD 128K+): 3/6/12m
2. Fubon+ 港元 (any funds): take highest tier (500K+)
3. Fubon+ 美元 (any funds): take highest tier (65K+)
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

        # Format: 存款期 三個月 六個月 十二個月
        #         港元    2.8%   2.8%    2.8%
        #         美元    4%     /      /
        hkd_rates = _extract_nf_row(nf_section, '港元')
        usd_rates = _extract_nf_row(nf_section, '美元')

        for period, rate in hkd_rates.items():
            hkd[period] = {'rate': rate, 'new_funds': True}
        for period, rate in usd_rates.items():
            usd[period] = {'rate': rate, 'new_funds': True}

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


def _extract_nf_row(section, currency):
    """Extract new fund rates for a currency from the new fund section.

    Format in text:
    存款期	三個月	六個月	十二個月
    港元	2.8%	2.8%	2.8%
    美元	4%	/	/
    """
    rates = {}
    # Find the currency row
    c_idx = section.find(currency)
    if c_idx < 0:
        return rates

    row = section[c_idx:c_idx + 200]

    # Match pattern: 港元	2.8%	2.8%	2.8% or 港元\n2.8%\n2.8%\n2.8%
    pcts = re.findall(r'(\d+(?:\.\d+)?)%', row)

    period_order = ['3m', '6m', '12m']
    for i, pct in enumerate(pcts):
        if i < len(period_order):
            rates[period_order[i]] = float(pct)

    return rates


def _extract_tier_rates(section, rates, currency):
    """Extract the highest tier rates from a Fubon+ section."""
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
                rates[key] = {'rate': val, 'new_funds': False}
            elif existing.get('new_funds') is True and existing.get('rate', 0) > val:
                existing['any_funds_rate'] = val
            elif val > existing.get('rate', 0):
                rates[key] = {'rate': val, 'new_funds': False}
