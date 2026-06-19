"""工銀亞洲 ICBC Asia - Parser for new funds time deposit promotion rates.

Source page: https://www.icbcasia.com/hk/tc/personal/latest-promotion/new-funds-time-deposit.html

Promotion table structure (98天=3個月, 188天=6個月):
    客戶類別 | 存款金額 | 98天 | 188天
    工銀財富客戶 | 港幣3,000,000元或以上 | 2.90% | 2.80%
    工銀財富／理財金客戶 | 港幣800,000元或以上 | 2.85% | 2.75%
    工銀財富／理財金客戶 | 美元100,000元或以上 | 3.80% | 3.75%
    ...

Takes the highest rate per currency across all customer tiers.
"""
import re

def parse(text, tables=None, html=None):
    """Parse ICBC Asia new funds time deposit promotion rates.

    Maps 98天 → 3m, 188天 → 6m.
    Returns highest rate per currency across all tiers.
    """
    if not text:
        return None

    rates = {}
    note = '全新資金定期存款推廣（分行）'

    # ---- Strategy 1: Parse 98天/188天 promotion table ----
    # Build per-currency best rates
    hkd_best = {'3m': 0, '6m': 0}
    usd_best = {'3m': 0, '6m': 0}
    cny_best = {'3m': 0, '6m': 0}

    # Use tables if available (more reliable), otherwise fall back to text
    search_blocks = []
    if tables:
        for tbl in tables:
            search_blocks.append(tbl)
    search_blocks.append(text)

    for block in search_blocks:
        # HKD rows: 港幣<amount>  <rate98>%  <rate188>%
        for m in re.finditer(r'港\s*幣[\d,，]+(?:元)?(?:或以上)?\s*(\d+\.\d+)\s*%\s*(\d+\.\d+)\s*%', block):
            r98, r188 = float(m.group(1)), float(m.group(2))
            if r98 > hkd_best['3m']:
                hkd_best['3m'] = r98
            if r188 > hkd_best['6m']:
                hkd_best['6m'] = r188

        # USD rows: 美元<amount>  <rate98>%  <rate188>%
        for m in re.finditer(r'美\s*元[\d,，]+(?:元)?(?:或以上)?\s*(\d+\.\d+)\s*%\s*(\d+\.\d+)\s*%', block):
            r98, r188 = float(m.group(1)), float(m.group(2))
            if r98 > usd_best['3m']:
                usd_best['3m'] = r98
            if r188 > usd_best['6m']:
                usd_best['6m'] = r188

        # CNY rows: 人民幣<amount>  <rate98>%  <rate188>%
        for m in re.finditer(r'人\s*民\s*幣[\d,，]+(?:元)?(?:或以上)?\s*(\d+\.\d+)\s*%\s*(\d+\.\d+)\s*%', block):
            r98, r188 = float(m.group(1)), float(m.group(2))
            if r98 > cny_best['3m']:
                cny_best['3m'] = r98
            if r188 > cny_best['6m']:
                cny_best['6m'] = r188

    # Assemble result
    if hkd_best['3m'] > 0 or hkd_best['6m'] > 0:
        rates['hkd'] = {}
        if hkd_best['3m'] > 0:
            rates['hkd']['3m'] = {
                'rate': hkd_best['3m'],
                'min_deposit': 50000,
                'fund_type': 'new_funds',
            }
        if hkd_best['6m'] > 0:
            rates['hkd']['6m'] = {
                'rate': hkd_best['6m'],
                'min_deposit': 50000,
                'fund_type': 'new_funds',
            }

    if usd_best['3m'] > 0 or usd_best['6m'] > 0:
        rates['usd'] = {}
        if usd_best['3m'] > 0:
            rates['usd']['3m'] = {
                'rate': usd_best['3m'],
                'min_deposit': 15000,
                'fund_type': 'new_funds',
            }
        if usd_best['6m'] > 0:
            rates['usd']['6m'] = {
                'rate': usd_best['6m'],
                'min_deposit': 15000,
                'fund_type': 'new_funds',
            }

    if cny_best['3m'] > 0 or cny_best['6m'] > 0:
        rates['cny'] = {}
        if cny_best['3m'] > 0:
            rates['cny']['3m'] = {
                'rate': cny_best['3m'],
                'min_deposit': 50000,
                'fund_type': 'new_funds',
            }
        if cny_best['6m'] > 0:
            rates['cny']['6m'] = {
                'rate': cny_best['6m'],
                'min_deposit': 50000,
                'fund_type': 'new_funds',
            }

    # ---- Strategy 2: Fallback to old online deposit format (1m/3m/6m/12m) ----
    if not rates:
        hkd_lines = re.findall(r'港\s*幣\s+[\d,]+[^%]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', text)
        if hkd_lines:
            m = hkd_lines[-1]
            rates['hkd'] = {
                '1m': {'rate': float(m[0]), 'fund_type': 'existing_funds'},
                '3m': {'rate': float(m[2]), 'fund_type': 'existing_funds'},
                '6m': {'rate': float(m[3]), 'fund_type': 'existing_funds'},
                '12m': {'rate': float(m[4]), 'fund_type': 'existing_funds'},
            }

        usd_lines = re.findall(r'美\s*元\s+[\d,]+[^%]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', text)
        if usd_lines:
            m = usd_lines[-1]
            rates['usd'] = {
                '1m': {'rate': float(m[0]), 'fund_type': 'existing_funds'},
                '3m': {'rate': float(m[2]), 'fund_type': 'existing_funds'},
                '6m': {'rate': float(m[3]), 'fund_type': 'existing_funds'},
                '12m': {'rate': float(m[4]), 'fund_type': 'existing_funds'},
            }
        note = '網上銀行特惠利率（工銀財富客戶）'

    if rates:
        rates['note'] = note
        return rates
    return None
