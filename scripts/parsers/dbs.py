"""星展銀行 DBS - Parser for online time deposit rates.

Page: https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo

Two rate sources:
1. Base table (新資金/現有資金/續存 tab): Standard rates for HKD 50K+
2. New funds promo section: Special rates for HKD 500K+ / USD 65K+

Parser extracts BOTH rates and stores in new structure:
- new_funds: from promo section (4m/6m at 3.0% / 4.0%)
- existing_funds: from base table (all periods)

Example output:
{
  'hkd': {
    '3m': {
      'new_funds': None,
      'existing_funds': {'rate': 2.5, 'min_deposit': 50000},
      'exchange': None
    },
    '4m': {
      'new_funds': {'rate': 3.0, 'min_deposit': 1000000},
      'existing_funds': {'rate': 2.45, 'min_deposit': 50000},
      'exchange': None
    },
    '6m': {
      'new_funds': {'rate': 3.0, 'min_deposit': 1000000},
      'existing_funds': {'rate': 2.45, 'min_deposit': 50000},
      'exchange': None
    }
  },
  '_use_new_structure': True
}
"""
import re


def parse(text, tables=None, html=None):
    """Parse DBS HK online time deposit rates."""
    if not text:
        return None

    rates = {}
    
    # === Extract base table rates (現有資金/續存) ===
    # This is the standard rate table for HKD 50K+
    base_hkd = {}
    base_usd = {}
    
    # Find the table section with "存款期" header
    table_idx = text.find('存款期')
    if table_idx >= 0:
        table_section = text[table_idx:table_idx + 2000]
        
        # Extract rates: X個月 X.XX%
        for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'),
                               ('4m', '4個月'), ('6m', '6個月'), ('9m', '9個月'),
                               ('12m', '12個月')]:
            # Pattern: "3個月\t2.50%\tQ6135\t2.50%\tR6135"
            m = re.search(rf'{label}\s+(\d+\.\d+)%', table_section)
            if m:
                base_hkd[period] = float(m.group(1))
    
    # Extract USD base rates (if available)
    # Usually in separate table or from HKET
    
    # === Extract new funds promo rates ===
    nf_hkd = {}
    nf_usd = {}
    
    # Find "網上新資金定期存款優惠" section
    nf_idx = text.find('網上新資金定期存款優惠')
    if nf_idx < 0:
        nf_idx = text.find('新資金定期存款優惠')
    
    if nf_idx >= 0:
        nf_section = text[nf_idx:nf_idx + 1000]
        nf_clean = re.sub(r'\s+', ' ', nf_section)
        
        # Pattern: "4或6個月 3.00% 4.00%"
        m = re.search(r'(\d+)或(\d+)個月\s+(\d+\.\d+)%\s+(\d+\.\d+)%', nf_clean)
        if m:
            p1 = _days_to_period(int(m.group(1)) * 30)
            p2 = _days_to_period(int(m.group(2)) * 30)
            nf_hkd[p1] = float(m.group(3))
            nf_hkd[p2] = float(m.group(3))
            nf_usd[p1] = float(m.group(4))
            nf_usd[p2] = float(m.group(4))
    
    # === Build rates with NEW STRUCTURE ===
    if base_hkd or nf_hkd:
        rates['hkd'] = {}
        
        for period in ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']:
            rates['hkd'][period] = {
                'new_funds': None,
                'existing_funds': None,
                'exchange': None,
            }
            
            # Add existing_funds rate from base table
            if period in base_hkd:
                rates['hkd'][period]['existing_funds'] = {
                    'rate': base_hkd[period],
                    'min_deposit': 50000,
                    'note': '網上定存特惠年利率',
                }
            
            # Add new_funds rate from promo section
            if period in nf_hkd:
                rates['hkd'][period]['new_funds'] = {
                    'rate': nf_hkd[period],
                    'min_deposit': 1000000,
                    'note': '新資金定期存款優惠（100萬港元以上）',
                }
    
    if base_usd or nf_usd:
        rates['usd'] = {}
        
        for period in ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']:
            rates['usd'][period] = {
                'new_funds': None,
                'existing_funds': None,
                'exchange': None,
            }
            
            if period in base_usd:
                rates['usd'][period]['existing_funds'] = {
                    'rate': base_usd[period],
                    'min_deposit': 50000,
                    'note': '網上定存特惠年利率',
                }
            
            if period in nf_usd:
                rates['usd'][period]['new_funds'] = {
                    'rate': nf_usd[period],
                    'min_deposit': 65000,
                    'note': '新資金定期存款優惠（65,000美元以上）',
                }
                # If no existing_funds rate, estimate based on HKD pattern
                # HKD: new=3.0%, existing=2.45% (ratio ~0.82)
                # Apply similar ratio to USD
                if period not in base_usd:
                    estimated_existing = round(nf_usd[period] * 0.82, 2)
                    rates['usd'][period]['existing_funds'] = {
                        'rate': estimated_existing,
                        'min_deposit': 50000,
                        'note': '網上定存特惠年利率（估算）',
                    }
    
    if rates:
        rates['note'] = '網上定存特惠年利率'
        rates['_use_new_structure'] = True
        return rates
    
    return None


def _days_to_period(days):
    """Convert days to period key."""
    mapping = {
        7: '1w', 14: '2w', 30: '1m', 60: '2m', 90: '3m',
        120: '4m', 180: '6m', 270: '9m', 365: '12m',
    }
    return mapping.get(days)