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


def parse(text, tables=None, html=None, usd_rates=None, hkd_new_funds_rates=None):
    """Parse DBS HK online time deposit rates.
    
    Args:
        text: Scraped text from main page
        usd_rates: Optional dict of USD existing_funds rates from USD tab
                   e.g. {'1m': 3.0, '3m': 3.45, ...}
        hkd_new_funds_rates: Optional dict of HKD new_funds rates from 新資金 tab
                            e.g. {'1m': 2.0, '3m': 2.5, ...}
    """
    if not text:
        return None

    rates = {}
    
    # === Extract base table rates (現有資金/續存) ===
    # This is the standard rate table for HKD 50K+ / USD 6K+
    base_hkd = {}
    base_usd = {}
    
    # Find HKD rates from the base table
    table_idx = text.find('存款期')
    if table_idx >= 0:
        table_section = text[table_idx:table_idx + 2000]
        
        # Extract HKD rates: X個月 X.XX%
        for period, label in [('1m', '1個月'), ('2m', '2個月'), ('3m', '3個月'),
                               ('4m', '4個月'), ('6m', '6個月'), ('9m', '9個月'),
                               ('12m', '12個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', table_section)
            if m:
                base_hkd[period] = float(m.group(1))
    
    # Note: USD rates need to be scraped separately (different tab)
    # We'll use agent-browser to click USD tab and get those rates
    # For now, USD existing_funds rates will be extracted from agent-browser output
    
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
    
    # Merge HKD new funds base rates from 新資金 tab
    # Promo rates (nf_hkd) should override base new_funds rates for 4m/6m
    if hkd_new_funds_rates:
        for period, rate in hkd_new_funds_rates.items():
            if period not in nf_hkd:
                nf_hkd[period] = rate
    
    # Merge HKD new funds base rates from 新資金 tab
    # Promo rates (nf_hkd) should override base new_funds rates for 4m/6m
    if hkd_new_funds_rates:
        for period, rate in hkd_new_funds_rates.items():
            if period not in nf_hkd:
                nf_hkd[period] = rate
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
    
    if base_usd or nf_usd or usd_rates:
        rates['usd'] = {}
        
        for period in ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']:
            rates['usd'][period] = {
                'new_funds': None,
                'existing_funds': None,
                'exchange': None,
            }
            
            # Use usd_rates if provided (from USD tab)
            if usd_rates and period in usd_rates:
                rates['usd'][period]['existing_funds'] = {
                    'rate': usd_rates[period],
                    'min_deposit': 6000,
                    'note': '網上定存特惠年利率',
                }
            elif period in base_usd:
                rates['usd'][period]['existing_funds'] = {
                    'rate': base_usd[period],
                    'min_deposit': 6000,
                    'note': '網上定存特惠年利率',
                }
            
            if period in nf_usd:
                rates['usd'][period]['new_funds'] = {
                    'rate': nf_usd[period],
                    'min_deposit': 65000,
                    'note': '新資金定期存款優惠（65,000美元以上）',
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