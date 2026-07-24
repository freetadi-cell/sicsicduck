"""平安數字銀行 PAO Bank - Parser for time deposit rates.

Updated 2026-07-24 to handle text format from requests.

Format:
港元新資金定期存款優惠
1 個月港元定期存款：年利率 2.50%
3 個月港元定期存款：年利率 3.00%
6 個月港元定期存款：年利率 2.90%
12 個月港元定期存款：年利率 3.15%
"""
import re


def parse(text, tables=None, html=None):
    """Parse PAO Bank time deposit rates."""
    if not text:
        return None
    
    rates = {}
    
    # Look for new fund promo rates
    # Pattern: "1 個月港元定期存款：年利率 2.50%"
    hkd_rates = {}
    
    for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
        m = re.search(rf'{label}\s*個月港元定期存款[：:]\s*年利率\s*(\d+\.\d+)%', text)
        if m:
            hkd_rates[period] = {
                'rate': float(m.group(1)),
                'fund_type': 'new_funds',
                'min_deposit': 100,
                'note': '新資金定期存款優惠',
                'source': 'bank'
            }
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    return rates if rates else None
