"""星展銀行 DBS - Parser for online time deposit rates.

Page: https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo#exist_fund

Two rate tiers on page:
1. 網上定存優惠 (HKD 50,000+) — standard online TD rates
2. 現有資金定期存款優惠 (HKD 1,000,000+ / USD 128,000+) — higher rates for large deposits

Parser extracts the best available rate for each period.
"""
import re


def parse(text, tables=None):
    """Parse DBS HK online time deposit rates.

    Page format (June 2026):
    現有資金定期存款優惠
    港元 高達 2.80%
    美元 高達 3.80%
    4或6個月  2.80%  3.80%

    網上定存優惠 (HKD 50,000+):
    存款期  特惠年利率*  優惠編號  特惠年利率*  優惠編號
    1個月  2.00%  Q6111  2.00%  R6111
    3個月  2.40%  Q6131  2.40%  R6131
    6個月  2.30%  Q6161  2.30%  R6161
    12個月  2.30%  Q61Y1  2.30%  R61Y1
    """
    if not text:
        return None

    rates = {}

    # === 現有資金定期存款優惠 (HKD 1M+ / USD 128K+) ===
    exist_idx = text.find('現有資金定期存款優惠')
    exist_hkd = {}
    exist_usd = {}
    if exist_idx >= 0:
        exist_section = text[exist_idx:exist_idx + 500]

        # Pattern: 4或6個月  2.80%  3.80%
        m = re.search(r'4或6個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', exist_section)
        if m:
            exist_hkd['4m'] = float(m.group(1))
            exist_hkd['6m'] = float(m.group(1))
            exist_usd['4m'] = float(m.group(2))
            exist_usd['6m'] = float(m.group(2))

    # === 網上定存優惠 table (HKD 50K+) ===
    hkd_rates = {}
    for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'),
                           ('4m', '4個月'), ('6m', '6個月'), ('9m', '9個月'),
                           ('12m', '12個月')]:
        m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\w+\d+', text)
        if m:
            hkd_rates[period] = float(m.group(1))

    # Merge: use the higher rate between standard and existing fund promo
    if hkd_rates:
        rates['hkd'] = {}
        for period, rate in hkd_rates.items():
            rates['hkd'][period] = {
                'rate': rate,
                'new_funds': False,
            }
        # Override with higher existing fund promo rates
        for period, rate in exist_hkd.items():
            if period in rates['hkd']:
                if rate > rates['hkd'][period]['rate']:
                    rates['hkd'][period]['rate'] = rate
                    rates['hkd'][period]['exist_fund_promo'] = True

    # USD: only from existing fund promo (page doesn't show USD table separately)
    if exist_usd:
        rates['usd'] = {}
        for period, rate in exist_usd.items():
            rates['usd'][period] = {
                'rate': rate,
                'new_funds': False,
                'note': '現有資金定期存款優惠（128,000美元以上）',
            }

    # Fallback: old promo format
    if not rates.get('hkd') and not rates.get('usd'):
        hkd_promo = re.search(r'港元定存(\d+\.\d+)%及美元(\d+\.\d+)%', text)
        if hkd_promo:
            rates['hkd'] = {'3m': float(hkd_promo.group(1))}
            rates['usd'] = {'3m': float(hkd_promo.group(2))}
            rates['note'] = '新資金定期存款優惠（50萬港元/6.5萬美元以上）'

    if rates and ('hkd' in rates or 'usd' in rates):
        rates['note'] = '網上定存特惠年利率'
        return rates

    return None
