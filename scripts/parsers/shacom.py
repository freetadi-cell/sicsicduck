"""上海商業銀行 Shanghai Commercial Bank - Parser for deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse Shanghai Commercial Bank online/mobile deposit rates.
    
    Page has two sections:
    1. 新資金定期存款年利率優惠 - USD and CNY
    2. 個人網上銀行 / 流動銀行定期存款年利率優惠 - HKD, USD, CNY
    
    Format in markdown:
    ### 個人網上銀行 / 流動銀行定期存款年利率優惠
     1 個月  3 個月  6 個月  12 個月
     港元 2.13% 2.78% 2.93% 2.98%
     美元 2.98% 3.48% 3.53% 3.53%
     人民幣 0.58% 0.98% 1.03% 1.03%
    """
    if not text:
        return None
    
    rates = {}
    
    # === 新資金定期存款年利率優惠 ===
    # Find the section
    new_funds_idx = text.find('新資金定期存款年利率優惠')
    if new_funds_idx >= 0:
        new_funds_end = text.find('個人網上銀行', new_funds_idx)
        new_funds_section = text[new_funds_idx:new_funds_end if new_funds_end > 0 else new_funds_idx + 1500]
        
        # USD rates in new funds section
        usd_m = re.search(r'美元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', new_funds_section)
        if usd_m:
            rates['usd'] = {
                '1m': {'rate': float(usd_m.group(1)), 'min_deposit': 2000, 'note': '新資金定期存款', 'source': 'bank'},
                '3m': {'rate': float(usd_m.group(2)), 'min_deposit': 2000, 'note': '新資金定期存款', 'source': 'bank'},
                '6m': {'rate': float(usd_m.group(3)), 'min_deposit': 2000, 'note': '新資金定期存款', 'source': 'bank'},
                '12m': {'rate': float(usd_m.group(4)), 'min_deposit': 2000, 'note': '新資金定期存款', 'source': 'bank'},
            }
        
        # CNY rates in new funds section
        cny_m = re.search(r'人民幣\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', new_funds_section)
        if cny_m:
            rates['cny'] = {
                '1m': {'rate': float(cny_m.group(1)), 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'bank'},
                '3m': {'rate': float(cny_m.group(2)), 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'bank'},
                '6m': {'rate': float(cny_m.group(3)), 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'bank'},
                '12m': {'rate': float(cny_m.group(4)), 'min_deposit': 10000, 'note': '新資金定期存款', 'source': 'bank'},
            }
    
    # === 個人網上銀行 / 流動銀行定期存款年利率優惠 ===
    # Find online banking section
    online_idx = text.find('個人網上銀行')
    if online_idx >= 0:
        online_section = text[online_idx:online_idx + 1500]
        
        # HKD rates in online banking section
        hkd_m = re.search(r'港元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', online_section)
        if hkd_m:
            rates['hkd'] = {
                '1m': {'rate': float(hkd_m.group(1)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '3m': {'rate': float(hkd_m.group(2)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '6m': {'rate': float(hkd_m.group(3)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '12m': {'rate': float(hkd_m.group(4)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
            }
        
        # Update USD rates if online banking has better rates
        usd_online_m = re.search(r'美元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', online_section)
        if usd_online_m and 'usd' not in rates:
            rates['usd'] = {
                '1m': {'rate': float(usd_online_m.group(1)), 'min_deposit': 2000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '3m': {'rate': float(usd_online_m.group(2)), 'min_deposit': 2000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '6m': {'rate': float(usd_online_m.group(3)), 'min_deposit': 2000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '12m': {'rate': float(usd_online_m.group(4)), 'min_deposit': 2000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
            }
        
        # Update CNY rates if online banking has better rates
        cny_online_m = re.search(r'人民幣\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', online_section)
        if cny_online_m and 'cny' not in rates:
            rates['cny'] = {
                '1m': {'rate': float(cny_online_m.group(1)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '3m': {'rate': float(cny_online_m.group(2)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '6m': {'rate': float(cny_online_m.group(3)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
                '12m': {'rate': float(cny_online_m.group(4)), 'min_deposit': 10000, 'note': '網上銀行/流動銀行定期存款', 'source': 'bank'},
            }
    
    if rates:
        return rates
    return None
