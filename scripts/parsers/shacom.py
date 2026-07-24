"""上海商業銀行 Shanghai Commercial Bank - Parser for deposit rates.

Updated 2026-07-24 to handle multi-line format from requests.

Format:
新資金定期存款年利率優惠
 1 個月  3 個月  6 個月  12 個月
 美元
 3.30%
 3.65%
 3.70%
 3.70%
 人民幣
 0.75%
 1.25%
 1.30%
 1.30%
"""
import re


def parse(text, tables=None, html=None):
    """Parse Shanghai Commercial Bank deposit rates from text."""
    if not text:
        return None
    
    rates = {}
    
    # === 新資金定期存款年利率優惠 ===
    new_funds_idx = text.find('新資金定期存款年利率優惠')
    if new_funds_idx >= 0:
        # Find next section
        next_section = text.find('個人網上銀行', new_funds_idx)
        if next_section < 0:
            next_section = len(text)
        section = text[new_funds_idx:next_section]
        
        # Parse multi-line format: 美元\n 3.30%\n 3.65%\n 3.70%\n 3.70%
        # USD
        usd_match = re.search(r'美元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if not usd_match:
            # Try multi-line format
            usd_match = re.search(r'美元\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%', section)
        
        if usd_match:
            rates['usd'] = {
                '1m': {'rate': float(usd_match.group(1)), 'fund_type': 'new_funds', 'min_deposit': 50000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '3m': {'rate': float(usd_match.group(2)), 'fund_type': 'new_funds', 'min_deposit': 50000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '6m': {'rate': float(usd_match.group(3)), 'fund_type': 'new_funds', 'min_deposit': 50000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '12m': {'rate': float(usd_match.group(4)), 'fund_type': 'new_funds', 'min_deposit': 50000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
            }
        
        # CNY
        cny_match = re.search(r'人民幣\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if not cny_match:
            cny_match = re.search(r'人民幣\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%', section)
        
        if cny_match:
            rates['cny'] = {
                '1m': {'rate': float(cny_match.group(1)), 'fund_type': 'new_funds', 'min_deposit': 100000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '3m': {'rate': float(cny_match.group(2)), 'fund_type': 'new_funds', 'min_deposit': 100000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '6m': {'rate': float(cny_match.group(3)), 'fund_type': 'new_funds', 'min_deposit': 100000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
                '12m': {'rate': float(cny_match.group(4)), 'fund_type': 'new_funds', 'min_deposit': 100000, 'note': '新資金定期存款（分行）', 'source': 'bank'},
            }
    
    # === 個人網上銀行 / 流動銀行定期存款年利率優惠 ===
    online_idx = text.find('個人網上銀行')
    if online_idx >= 0:
        section = text[online_idx:online_idx + 2000]
        
        # HKD
        hkd_match = re.search(r'港元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if not hkd_match:
            hkd_match = re.search(r'港元\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%', section)
        
        if hkd_match:
            rates['hkd'] = {
                '1m': {'rate': float(hkd_match.group(1)), 'min_deposit': 1000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                '3m': {'rate': float(hkd_match.group(2)), 'min_deposit': 1000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                '6m': {'rate': float(hkd_match.group(3)), 'min_deposit': 1000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                '12m': {'rate': float(hkd_match.group(4)), 'min_deposit': 1000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
            }
        
        # USD (if not in new funds)
        if 'usd' not in rates:
            usd_match = re.search(r'美元\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
            if not usd_match:
                usd_match = re.search(r'美元\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%', section)
            
            if usd_match:
                rates['usd'] = {
                    '1m': {'rate': float(usd_match.group(1)), 'min_deposit': 5000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '3m': {'rate': float(usd_match.group(2)), 'min_deposit': 5000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '6m': {'rate': float(usd_match.group(3)), 'min_deposit': 5000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '12m': {'rate': float(usd_match.group(4)), 'min_deposit': 5000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                }
        
        # CNY (if not in new funds)
        if 'cny' not in rates:
            cny_match = re.search(r'人民幣\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
            if not cny_match:
                cny_match = re.search(r'人民幣\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%\s*\n\s*(\d+\.\d+)%', section)
            
            if cny_match:
                rates['cny'] = {
                    '1m': {'rate': float(cny_match.group(1)), 'min_deposit': 10000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '3m': {'rate': float(cny_match.group(2)), 'min_deposit': 10000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '6m': {'rate': float(cny_match.group(3)), 'min_deposit': 10000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                    '12m': {'rate': float(cny_match.group(4)), 'min_deposit': 10000, 'note': '個人網上銀行/流動銀行定期存款', 'source': 'bank'},
                }
    
    return rates if rates else None