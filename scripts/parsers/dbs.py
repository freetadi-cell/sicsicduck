"""星展銀行 DBS - Parser for online time deposit rates.

Page: https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo#exist_fund

Three rate tiers on page:
1. 網上定存優惠 (HKD 50,000+) — standard online TD rates
2. 現有資金定期存款優惠 (HKD 1,000,000+ / USD 128,000+) — existing fund large deposit
3. 新資金定期存款優惠 (HKD 1,000,000+ / USD 128,000+) — new fund large deposit

Parser extracts the best available rate for each period.
Uses data-rate attributes in HTML for new fund rates (tab content may be hidden).
"""
import re


def parse(text, tables=None, html=None):
    """Parse DBS HK online time deposit rates.

    Page format (June 2026):
    現有資金定期存款優惠:
      港元 高達 2.80%, 4或6個月 2.80%
      美元 高達 3.80%, 4或6個月 3.80%

    新資金定期存款優惠 (from data-rate attrs in HTML):
      港元 高達 3.00%, 4或6個月 3.00%
      美元 高達 4.00%, 4或6個月 4.00%

    網上定存優惠 table (HKD 50K+):
      1個月 2.00% | 3個月 2.40% | 6個月 2.30% | 12個月 2.30%
    """
    if not text:
        return None

    rates = {}

    # === 網上定存優惠 table (HKD 50K+) ===
    hkd_rates = {}
    for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'),
                           ('4m', '4個月'), ('6m', '6個月'), ('9m', '9個月'),
                           ('12m', '12個月')]:
        m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\w+\d+', text)
        if m:
            hkd_rates[period] = float(m.group(1))

    # === 新資金定期存款優惠 (from data-rate attrs in HTML) ===
    nf_hkd = {}
    nf_usd = {}
    if html:
        # data-rate attrs: data-currency="HKD" data-fund="new" data-days="120" data-rate="3.00"
        for m in re.finditer(
            r'data-currency="HKD"\s+data-days="(\d+)"\s+data-fund="new"\s+[^>]*data-rate="(\d+\.\d+)"',
            html
        ):
            days, rate = int(m.group(1)), float(m.group(2))
            period = _days_to_period(days)
            if period and rate > nf_hkd.get(period, 0):
                nf_hkd[period] = rate

        for m in re.finditer(
            r'data-currency="USD"\s+data-days="(\d+)"\s+data-fund="new"\s+[^>]*data-rate="(\d+\.\d+)"',
            html
        ):
            days, rate = int(m.group(1)), float(m.group(2))
            period = _days_to_period(days)
            if period and rate > nf_usd.get(period, 0):
                nf_usd[period] = rate

    # === 現有資金定期存款優惠 (HKD 1M+ / USD 128K+) ===
    exist_idx = text.find('現有資金定期存款優惠')
    exist_hkd = {}
    exist_usd = {}
    if exist_idx >= 0:
        exist_section = text[exist_idx:exist_idx + 500]
        m = re.search(r'4或6個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', exist_section)
        if m:
            exist_hkd['4m'] = float(m.group(1))
            exist_hkd['6m'] = float(m.group(1))
            exist_usd['4m'] = float(m.group(2))
            exist_usd['6m'] = float(m.group(2))

    # === Build HKD rates ===
    if hkd_rates:
        rates['hkd'] = {}
        for period, rate in hkd_rates.items():
            rates['hkd'][period] = {
                'rate': rate,
                'new_funds': False,
            }
        # Override with higher new fund promo rates
        for period, rate in nf_hkd.items():
            if period in rates['hkd']:
                if rate > rates['hkd'][period]['rate']:
                    rates['hkd'][period]['rate'] = rate
                    rates['hkd'][period]['new_funds'] = True
                    rates['hkd'][period]['note'] = '新資金定期存款優惠（100萬港元以上）'
        # Override with higher existing fund promo rates
        for period, rate in exist_hkd.items():
            if period in rates['hkd']:
                curr = rates['hkd'][period].get('rate', 0)
                if rate > curr:
                    rates['hkd'][period]['rate'] = rate
                    rates['hkd'][period]['new_funds'] = False
                    rates['hkd'][period]['note'] = '現有資金定期存款優惠（100萬港元以上）'

    # === Build USD rates ===
    if nf_usd or exist_usd:
        rates['usd'] = {}
        all_usd = {}
        for period, rate in nf_usd.items():
            all_usd[period] = {
                'rate': rate,
                'new_funds': True,
                'note': '新資金定期存款優惠（128,000美元以上）',
            }
        for period, rate in exist_usd.items():
            if period not in all_usd or rate > all_usd[period]['rate']:
                all_usd[period] = {
                    'rate': rate,
                    'new_funds': False,
                    'note': '現有資金定期存款優惠（128,000美元以上）',
                }
        rates['usd'] = all_usd

    if rates and ('hkd' in rates or 'usd' in rates):
        rates['note'] = '網上定存特惠年利率'
        return rates

    return None


def _days_to_period(days):
    """Convert days to period key."""
    mapping = {
        7: '1w', 14: '2w', 30: '1m', 60: '2m', 90: '3m',
        120: '4m', 180: '6m', 270: '9m', 365: '12m',
    }
    return mapping.get(days)
