"""上海商業銀行 Shanghai Commercial Bank - Parser for deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse Shanghai Commercial Bank online/mobile deposit rates.
    
    Page has:
    個人網上銀行 / 流動銀行定期存款年利率優惠
    
            1 個月  3 個月  6 個月  12 個月
    港元    1.68%   2.48%   2.48%   2.43%
    美元    2.98%   3.38%   3.33%   3.23%
    """
    if not text:
        return None
    
    rates = {}
    note = '網上銀行/流動銀行定期存款利率'
    
    # Find online banking section
    # Find the SECOND occurrence of '個人網上銀行' (first is in nav, second is the actual rates)
    first_idx = text.find('個人網上銀行')
    if first_idx < 0:
        return None
    second_idx = text.find('個人網上銀行', first_idx + 1)
    section = text[second_idx:second_idx+3000] if second_idx > 0 else text[first_idx:first_idx+3000]
    
    # HKD rates
    hkd_m = re.search(r'港元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if hkd_m:
        rates['hkd'] = {
            '1m': float(hkd_m.group(1)),
            '3m': float(hkd_m.group(2)),
            '6m': float(hkd_m.group(3)),
            '12m': float(hkd_m.group(4)),
        }
    
    # USD rates
    usd_m = re.search(r'美元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if usd_m:
        rates['usd'] = {
            '1m': float(usd_m.group(1)),
            '3m': float(usd_m.group(2)),
            '6m': float(usd_m.group(3)),
            '12m': float(usd_m.group(4)),
        }
    
    if rates:
        rates['note'] = note
        return rates
    return None
