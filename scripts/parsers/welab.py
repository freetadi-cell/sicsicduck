"""匯立銀行 WeLab Bank - Parser for GoSave 2.0 time deposit rates.

Updated 2026-07-24:
- 官網 JS 渲染，利率表可能抓唔到
- 改用 HKET 作為主要數據源
- 保留官網 parser 作為後備

Page: https://www.welab.bank/zh/feature/gosave_2/
"""
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse WeLab Bank GoSave 2.0 rates.
    
    Priority:
    1. Try HKET article parsing (hket_common)
    2. Fallback to original text parsing
    """
    if not text:
        return None
    
    # === Try HKET parsing first ===
    # Check if this looks like an HKET article
    if '匯立銀行' in text or 'WeLab' in text or '每日定存' in text:
        rates = parse_hket_article(text, bank_name='匯立銀行')
        if rates and rates.get('hkd'):
            # Convert HKET format to standard format
            return _convert_hket_to_standard(rates)
    
    # === Fallback: original text parsing ===
    rates = {}
    note = 'GoSave 2.0 定期存款'
    
    # HKD rates - look for Chinese format: 3個月 2.85%
    hkd_rates = {}
    for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Pattern: 3個月\t2.85%⁵ or 3個月 2.85%
        pattern = rf'{label}[\s\t]+(\d+\.\d+)%'
        m = re.search(pattern, text)
        if m:
            hkd_rates[period] = {
                'rate': float(m.group(1)),
                'min_deposit': 1,
                'note': note,
                'source': 'bank'
            }
    
    # Fallback: try English format
    if not hkd_rates:
        for period, label in [('1m', '1-month'), ('3m', '3-month'), ('6m', '6-month'), ('12m', '12-month')]:
            pattern = rf'{label}\s+(\d+\.\d+)%'
            m = re.search(pattern, text)
            if m:
                hkd_rates[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 1,
                    'note': note,
                    'source': 'bank'
                }
    
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    if rates:
        return rates
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