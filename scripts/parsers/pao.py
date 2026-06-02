"""平安數字銀行 PAO Bank - Parser for time deposit rates.

Supports two page formats:
1. 新資金定期存款優惠頁 (retail-td-newfund.html)
2. 一般定期存款頁 (retail-savings.html)
"""
import re


def parse(text, tables=None):
    """Parse PAO Bank (平安數字銀行) time deposit rates.

    新資金優惠頁格式:
    1 個月港元定期存款：年利率 2.50%
    3 個月港元定期存款：年利率 2.90%
    ...
    存款期  存款金額  年利率
    1個月  新資金 HKD 100 - HKD 100,000,000  2.50%*

    一般定期頁格式:
    定期存款年利率
    存款期  港元 (年利率)  人民幣 (年利率)  美元 (年利率)
    1個月  2.40%  0.10%  2.80%
    """
    if not text:
        return None

    rates = {}

    # === 新資金定期存款優惠 ===
    nf_idx = text.find('新資金定期存款優惠')
    if nf_idx >= 0:
        nf_section = text[nf_idx:nf_idx + 2000]
        hkd_nf = {}

        # Match patterns like "1 個月港元定期存款：年利率 2.50%"
        for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
            m = re.search(
                rf'{label}\s*個月港元定期存款[：:]\s*年利率\s*(\d+\.\d+)%',
                nf_section
            )
            if m:
                hkd_nf[period] = float(m.group(1))

        # Fallback: try table format "1個月  新資金 HKD 100 - HKD 100,000,000  2.50%"
        if not hkd_nf:
            for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
                m = re.search(rf'{label}\s+新資金[^\d]*?(\d+\.\d+)%', nf_section)
                if m:
                    hkd_nf[period] = float(m.group(1))

        if hkd_nf:
            rates['hkd'] = {}
            for period, rate in hkd_nf.items():
                rates['hkd'][period] = {
                    'rate': rate,
                    'new_funds': True,
                }
            rates['note'] = '新資金定期存款優惠'
            # Extract promo end date if available
            date_m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', nf_section)
            if date_m:
                rates['hkd_note'] = f'新資金定期優惠 (至 {date_m.group(2)}/{date_m.group(3)})'
            else:
                rates['hkd_note'] = '新資金定期存款優惠'

    # === 一般定期存款年利率 ===
    td_idx = text.find('定期存款年利率')
    if td_idx >= 0:
        td_section = text[td_idx:td_idx + 800]
        hkd_std = {}
        usd_std = {}

        for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\d+\.\d+%\s+(\d+\.\d+)%', td_section)
            if m:
                hkd_std[period] = float(m.group(1))
                usd_std[period] = float(m.group(2))

        # If we already have new fund rates, store standard as any_funds_rate
        if 'hkd' in rates:
            for period, rate in hkd_std.items():
                if period in rates['hkd'] and isinstance(rates['hkd'][period], dict):
                    rates['hkd'][period]['any_funds_rate'] = rate
        elif hkd_std:
            rates['hkd'] = hkd_std
            rates['note'] = '定期存款年利率'

        if usd_std:
            rates['usd'] = usd_std
            if 'note' not in rates:
                rates['note'] = '定期存款年利率'

    if rates and ('hkd' in rates or 'usd' in rates):
        return rates
    return None
