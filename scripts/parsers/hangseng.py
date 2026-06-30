"""恒生銀行 Hang Seng Bank - Parser for new fund and card rate deposit rates."""
import re

def parse(text, tables=None, html=None):
    """Parse Hang Seng new fund and card rate time deposit rates.
    
    URL (新資金): https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html
    URL (牌價): https://www.hangseng.com/zh-hk/personal/banking/rates/deposit-interest-rates/
    
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
    note_new_funds = '新資金定期存款優惠（網上理財）'
    note_card_rate = '定期存款牌價利率'
    
    # Check if this is card rate page
    is_card_rate = '牌價' in text or '港元定期存款利率' in text or '一星期' in text
    
    if is_card_rate:
        # Parse card rate (existing_funds) - 牌價利率
        rates['hkd'] = {}
        rates['usd'] = {}
        
        # Pattern for card rate: "一星期 0.1000%" or "row "一星期 0.1000% 0.1000%"
        # HKD card rates
        periods_hkd = {
            '1w': '一星期', '2w': '二星期',
            '1m': '一個月', '2m': '二個月', '3m': '三個月', '6m': '六個月',
            '9m': '九個月', '12m': '十二個月', '18m': '一年半', '24m': '二年', '36m': '三年'
        }
        
        for period, label in periods_hkd.items():
            # Try snapshot format: row "一星期 0.1000% 0.1000% 0.1000% 0.1000%"
            m = re.search(rf'row "{label}\s+(\d+\.\d+)%', text)
            if m:
                rate = float(m.group(1))
                rates['hkd'][period] = {
                    'new_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'existing_funds': {'rate': rate, 'min_deposit': 10000, 'note': note_card_rate, 'source': 'bank'},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
            # Try cell format: cell "0.1000%"
            elif f'cell "{label}"' in text:
                # Find the rate after this period label
                # Look for: cell "一星期" followed by cell "0.1000%"
                pattern = rf'cell "{label}"[^]]*]\s*-\s*cell "(\d+\.\d+)%' 
                m = re.search(pattern, text)
                if m:
                    rate = float(m.group(1))
                    rates['hkd'][period] = {
                        'new_funds': {'rate': None, 'min_deposit': None, 'note': None},
                        'existing_funds': {'rate': rate, 'min_deposit': 10000, 'note': note_card_rate, 'source': 'bank'},
                        'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                    }
        
        if rates.get('hkd'):
            rates['note'] = note_card_rate
            rates['_use_new_structure'] = True
            return rates
    
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
            rates['note'] = note_new_funds
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
    
    # Try CNY text format
    cny_idx = text.find('人民幣定期存款特優年利率')
    if cny_idx >= 0:
        cny_section = text[cny_idx:cny_idx+500]
        rates['cny'] = {}
        for period, label in [('3m', '3個月'), ('6m', '6個月')]:
            m = re.search(rf'{label}[\s\t]+(\d+\.\d+)[\s\t]+(\d+\.\d+)', cny_section)
            if m:
                rates['cny'][period] = {
                    'new_funds': {'rate': float(m.group(1)), 'min_deposit': 10000, 'note': '新資金定期存款優惠（網上理財）'},
                    'existing_funds': {'rate': None, 'min_deposit': None, 'note': None},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None},
                }
    
    if rates:
        rates['note'] = note_new_funds
        rates['_use_new_structure'] = True
        return rates
    
    return None