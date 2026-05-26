"""星展銀行 DBS - Parser for online time deposit rates."""
import re

def parse(text, tables=None):
    """Parse DBS HK online time deposit rates from Chinese promo page.
    
    Page format:
    存款期  特惠年利率*  優惠編號  特惠年利率*  優惠編號
    1個月  2.40%  Q5115  2.40%  R5115
    3個月  2.25%  Q5135  2.25%  R5135
    6個月  2.30%  Q5165  2.30%  R5165
    12個月  2.30%  Q51Y5  2.30%  R51Y5
    
    Also has promo: 港元定存2.50%及美元3.90% (new fund, 500K+)
    """
    if not text:
        return None
    
    rates = {}
    
    # Try new fund promo first (better rates)
    hkd_promo = re.search(r'港元定存(\d+\.\d+)%及美元(\d+\.\d+)%', text)
    if hkd_promo:
        rates['hkd'] = {'3m': float(hkd_promo.group(1))}
        rates['usd'] = {'3m': float(hkd_promo.group(2))}
        rates['note'] = '新資金定期存款優惠（50萬港元/6.5萬美元以上）'
        return rates
    
    # Fallback: online rate table
    # Look for rate rows: 3個月  2.25%  Q5135  2.25%  R5135
    hkd_rates = {}
    for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'), 
                           ('4m', '4個月'), ('6m', '6個月'), ('12m', '12個月')]:
        m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\w+\s+(\d+\.\d+)%', text)
        if m:
            hkd_rates[period] = float(m.group(1))  # 一般星展客戶 rate
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
        rates['note'] = '網上定期存款特惠年利率'
        return rates
    
    # Last fallback: English promo text
    hkd_en = re.search(r'HKD\s+(\d+\.\d+)%\s*p\.a\.', text)
    usd_en = re.search(r'USD\s+(\d+\.\d+)%\s*p\.a\.', text)
    if hkd_en:
        rates['hkd'] = {'3m': float(hkd_en.group(1))}
    if usd_en:
        rates['usd'] = {'3m': float(usd_en.group(1))}
    if rates:
        rates['note'] = '網上定期存款特惠利率'
        return rates
    
    return None
