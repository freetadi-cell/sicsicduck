"""招商永隆 Wing Lung Bank - Parser for time deposit rates.

Page: https://www.cmbwinglungbank.com/ibanking/CnCoFiiDepratDsp.jsp
Data available via curl (no browser needed).

Each period has 4 tiers with (分行 rate, 手機App rate) pairs.
We take the highest tier's App rate.
"""
import re


def _parse_section(section, min_rate=0.5):
    """Parse rates from a currency section.
    Format: period分行手機App rate1_branch rate1_app rate2_branch rate2_app ...
    4 tiers per period, we want the last (highest tier) app rate.
    """
    rates = {}
    for period, label in [('1m', '1 個月'), ('2m', '2 個月'), ('3m', '3 個月'),
                           ('6m', '6 個月'), ('9m', '9 個月'), ('12m', '12 個月')]:
        idx = section.find(label)
        if idx < 0:
            continue
        # Get text from period label to next period label (or end)
        sub = section[idx + len(label):]
        # Find next period label to bound the section
        next_period = len(sub)
        for lbl in ['1 個月', '2 個月', '3 個月', '6 個月', '9 個月', '12 個月', '24 個月',
                     '美元', '人民幣', '澳元', '紐西蘭', '加元']:
            ni = sub.find(lbl)
            if 0 < ni < next_period:
                next_period = ni
        sub = sub[:next_period]

        # Find all rate pairs after "手機App"
        # Each row: 分行 rate, 手機App rate (repeated for each tier)
        # All numbers in sequence: b1, a1, b2, a2, b3, a3, b4, a4
        nums = re.findall(r'(\d+\.\d+)', sub)
        if len(nums) >= 2:
            # Take every 2nd number starting from index 1 (app rates)
            # Last app rate = nums[-1] if odd count, or nums[-1] for even
            app_rates = [float(nums[i]) for i in range(1, len(nums), 2)]
            if app_rates:
                # Take the highest tier (last app rate)
                rates[period] = app_rates[-1]
    return rates


def parse(text, tables=None):
    """Parse Wing Lung Bank time deposit rates."""
    if not text:
        return None

    rates = {}

    # === HKD section ===
    hkd_idx = text.find('定期存款')
    usd_idx = text.find('美元定期存款利率')
    if hkd_idx < 0:
        return None

    hkd_section = text[hkd_idx:usd_idx] if usd_idx > hkd_idx else text[hkd_idx:hkd_idx + 5000]
    hkd_rates = _parse_section(hkd_section)
    if hkd_rates:
        rates['hkd'] = hkd_rates

    # === USD section ===
    if usd_idx > 0:
        # Find end of USD section (next currency section)
        usd_end = len(text)
        for marker in ['人民幣定期存款利率', '澳元定期存款利率']:
            mi = text.find(marker, usd_idx)
            if mi > 0:
                usd_end = min(usd_end, mi)
        usd_section = text[usd_idx:usd_end]
        usd_rates = _parse_section(usd_section, min_rate=1.0)
        if usd_rates:
            rates['usd'] = usd_rates

    if rates:
        rates['note'] = '招商永隆銀行手機App定存利率'
        return rates
    return None
