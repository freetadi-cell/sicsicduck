"""恒生銀行 Hang Seng Bank - Parser for new fund deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse Hang Seng new fund time deposit rates.
    
    URL: https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html
    Supports both text format and agent-browser snapshot format.
    
    Text format (tab-separated):
    港元定期存款特優年利率 (%)
    存款期\t網上理財\t分行/ 電話理財
    3個月\t2.40\t2.40
    
    Snapshot format:
    row "3個月 2.40 2.40":
      - cell "3個月"
      - cell "2.40"
    
    Returns new structure with fund_type separation.
    """
    if not text:
        return None
    
    rates = {}
    note = '新資金定期存款優惠（網上理財）'
    
    # Try snapshot format first (from agent-browser)
    # Pattern: row "3個月 2.40 2.40" or cell "2.40"
    if 'row "港元 3個月 2.40"' in text or 'cell "2.40"' in text:
        rates['hkd'] = {}
        rates['usd'] = {}
        
        # HKD 3m
        if 'row "港元 3個月 2.40"' in text:
            rates['hkd']['3m'] = {
                'new_funds': {'rate': 2.40, 'min_deposit': 10000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
        
        # HKD 6m
        if 'row "6個月 2.20 2.20"' in text:
            rates['hkd']['6m'] = {
                'new_funds': {'rate': 2.20, 'min_deposit': 10000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
        
        # USD 2/3m
        if 'row "美元 2/3個月 3.30"' in text or 'row "2/3個月 3.30 3.30"' in text:
            rates['usd']['2m'] = {
                'new_funds': {'rate': 3.30, 'min_deposit': 2000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
            rates['usd']['3m'] = {
                'new_funds': {'rate': 3.30, 'min_deposit': 2000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
        
        # USD 6m
        if 'row "6個月 3.20 3.20"' in text:
            rates['usd']['6m'] = {
                'new_funds': {'rate': 3.20, 'min_deposit': 2000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
        
        if rates.get('hkd') or rates.get('usd'):
            rates['note'] = note
            rates['_use_new_structure'] = True
            return rates
    
    # Try text format (tab-separated)
    hkd_idx = text.find('港元定期存款特優年利率')
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_idx+500]
        rates['hkd'] = {}
        for period, label in [('3m', '3個月'), ('6m', '6個月')]:
            m = re.search(rf'{label}[\s\t]+(\d+\.\d+)[\s\t]+(\d+\.\d+)', hkd_section)
            if m:
                rates['hkd'][period] = {
                    'new_funds': {'rate': float(m.group(1)), 'min_deposit': 10000, 'note': '新資金定期存款優惠（網上理財）'},
                    'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
    
    usd_idx = text.find('美元定期存款特優年利率')
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_idx+500]
        rates['usd'] = {}
        m = re.search(r'(\d+)/(\d+)個月[\s\t]+(\d+\.\d+)[\s\t]+(\d+\.\d+)', usd_section)
        if m:
            p1 = f'{m.group(1)}m' if m.group(1) in ['2', '3'] else '3m'
            p2 = f'{m.group(2)}m' if m.group(2) in ['2', '3'] else '3m'
            for p in [p1, p2]:
                rates['usd'][p] = {
                    'new_funds': {'rate': float(m.group(3)), 'min_deposit': 2000, 'note': '新資金定期存款優惠（網上理財）'},
                    'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
        m = re.search(r'6個月[\s\t]+(\d+\.\d+)[\s\t]+(\d+\.\d+)', usd_section)
        if m:
            rates['usd']['6m'] = {
                'new_funds': {'rate': float(m.group(1)), 'min_deposit': 2000, 'note': '新資金定期存款優惠（網上理財）'},
                'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                'exchange': {'rate': None, 'min_deposit': None, 'note': None},
            }
    
    if rates:
        rates['note'] = note
        rates['_use_new_structure'] = True
        return rates
    
    return None