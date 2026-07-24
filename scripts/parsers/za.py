"""眾安銀行 ZA Bank - Parser for time deposit rates.

Updated 2026-07-24:
- 官網 JS 渲染，利率表可能抓唔到
- 改用 HKET 作為主要數據源
- 保留官網 parser 作為後備

Page: https://bank.za.group/
"""
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse ZA Bank time deposit rates.
    
    Priority:
    1. Try HKET article parsing (hket_common)
    2. Fallback to original text parsing
    """
    if not text:
        return None
    
    # === Try HKET parsing first ===
    # Check if this looks like an HKET article
    if '眾安銀行' in text or 'ZA Bank' in text or '每日定存' in text:
        rates = parse_hket_article(text, bank_name='眾安銀行')
        if rates and (rates.get('hkd') or rates.get('usd')):
            # Convert HKET format to standard format
            return _convert_hket_to_standard(rates)
    
    # === Fallback: original text parsing ===
    hkd = {}
    usd = {}

    # Look for time deposit rates
    td_idx = text.find('定期存款')
    if td_idx < 0:
        td_idx = text.find('定期')
    
    if td_idx >= 0:
        section = text[td_idx:td_idx + 3000]
        for period, label in [('1m', r'1\s*個?月'), ('2m', r'2\s*個?月'),
                               ('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'),
                               ('12m', r'12\s*個?月')]:
            m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
            if m:
                rate = float(m.group(1))
                if rate > 0:
                    hkd[period] = {
                        'rate': rate,
                        'min_deposit': 1,
                        'note': '眾安銀行定期存款',
                        'source': 'bank'
                    }

    # Try looking for HKD/USD specific sections
    for currency, store in [('hkd', hkd), ('usd', usd)]:
        curr_label = '港元' if currency == 'hkd' else '美元'
        curr_idx = text.find(curr_label)
        if curr_idx >= 0:
            section = text[curr_idx:curr_idx + 2000]
            for period, label in [('3m', r'3\s*個?月'), ('6m', r'6\s*個?月'), ('12m', r'12?\s*個?月')]:
                m = re.search(rf'{label}\s*[^%]*?(\d+\.?\d*)%', section)
                if m:
                    rate = float(m.group(1))
                    if rate > 0:
                        store[period] = {
                            'rate': rate,
                            'min_deposit': 1,
                            'note': '眾安銀行定期存款',
                            'source': 'bank'
                        }

    # Try tables
    if tables and not hkd:
        for table in tables:
            table_str = str(table)
            for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
                m = re.search(rf'{label}\s*個?月\s*[^%]*?(\d+\.?\d*)%', table_str)
                if m:
                    rate = float(m.group(1))
                    if rate > 0:
                        hkd[period] = {
                            'rate': rate,
                            'min_deposit': 1,
                            'note': '眾安銀行定期存款',
                            'source': 'bank'
                        }

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd

    if result:
        return result
    return None


def _convert_hket_to_standard(hket_rates):
    """Convert HKET format to standard format."""
    result = {}
    
    for currency in ['hkd', 'usd', 'cny']:
        if currency not in hket_rates:
            continue
        
        currency_rates = {}
        for period, period_data in hket_rates[currency].items():
            # Take the best rate (new_funds > existing_funds > general)
            best_rate = None
            best_data = None
            
            for fund_type in ['new_funds', 'existing_funds', 'general']:
                if fund_type in period_data:
                    data = period_data[fund_type]
                    rate = data.get('rate', 0)
                    if rate and (best_rate is None or rate > best_rate):
                        best_rate = rate
                        best_data = data
            
            if best_data:
                currency_rates[period] = {
                    'rate': best_data['rate'],
                    'min_deposit': best_data.get('min_deposit', 0),
                    'note': best_data.get('note', '定期存款'),
                    'source': 'hket'
                }
        
        if currency_rates:
            result[currency] = currency_rates
    
    return result if result else None