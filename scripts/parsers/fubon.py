"""富邦銀行 Fubon Bank - Parser for time deposit rates.

Page: https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html

Three sections:
1. 新資金定期存款優惠 (new funds): HKD/USD 3m only
2. Fubon+ 港元 (any funds, 4 tiers): take highest tier (500k+)
3. Fubon+ 美元 (any funds, 3 tiers): take highest tier (65k+)

We take the highest rate per period across all sections.
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
            hkd['3m'] = float(hkd_m.group(1))
        if usd_m:
            usd['3m'] = float(usd_m.group(1))

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

    The HTML table has each % on its own line. Tiers are delimited by
    tier labels like "港元10,000至50,000以下", "港元500,000 或以上".
    We split by tier labels and take the last tier (highest amount).
    """
    # Find tier boundaries
    tier_labels = re.split(r'(?:港元|美元)[\d,]+\s*(?:至[\d,]+\w*)?(?:\s*或?\s*以上)?', section)

    # The last tier_label chunk contains the highest tier rates
    if len(tier_labels) < 2:
        return

    last_tier = tier_labels[-1]

    # Find all percentages in the last tier
    pcts = re.findall(r'(\d+\.\d+)%', last_tier)

    if not pcts:
        # Try second-to-last
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
            if key not in rates or val > rates[key]:
                rates[key] = val
