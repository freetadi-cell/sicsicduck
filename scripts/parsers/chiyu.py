"""集友銀行 Chiyu Bank - Parser for time deposit rates.

Updated 2026-07-24:
- 官網可能只有兌換定期存款，新資金定期存款在 PDF 入面
- 改用 HKET 作為主要數據源
- 保留官網 parser 作為後備

Priority: 新資金定期存款 (higher tier) > 特優定期存款 (higher tier)
"""
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse Chiyu Bank time deposit rates.
    
    Priority:
    1. Try HKET article parsing (hket_common)
    2. Fallback to original text parsing
    """
    if not text:
        return None
    
    # === Try HKET parsing first ===
    # Check if this looks like an HKET article
    if '集友銀行' in text or 'Chiyu' in text or '每日定存' in text:
        rates = parse_hket_article(text, bank_name='集友銀行')
        if rates and (rates.get('hkd') or rates.get('usd')):
            # Convert HKET format to standard format
            return _convert_hket_to_standard(rates)
    
    # === Fallback: original text parsing ===
    rates = {}
    
    # Find the 外幣兌換定期存款 section
    exchange_idx = text.find('外幣兌換定期存款')
    if exchange_idx < 0:
        return None
    
    # Get the section with the rate table
    section = text[exchange_idx:exchange_idx + 1500]
    
    # Parse HKD rates: 港元\t2.08%\t5.00%
    # Look for pattern: 港元 followed by percentages
    hkd_match = re.search(r'港元[\s\t]+(\d+\.\d+)%[\s\t]+(\d+\.\d+)%', section)
    if hkd_match:
        rates['hkd'] = {
            '1m': {
                'rate': float(hkd_match.group(1)),
                'min_deposit': 10000,
                'note': '外幣兌換定期存款（1個月）',
                'source': 'bank',
                'conditions': ['exchange']
            },
            '1w': {
                'rate': float(hkd_match.group(2)),
                'min_deposit': 10000,
                'note': '外幣兌換定期存款（1星期）',
                'source': 'bank',
                'conditions': ['exchange']
            }
        }
    
    # Parse USD rates
    usd_match = re.search(r'美元[\s\t]+(\d+\.\d+)%[\s\t]+(\d+\.\d+)%', section)
    if usd_match:
        rates['usd'] = {
            '1m': {
                'rate': float(usd_match.group(1)),
                'min_deposit': 1000,
                'note': '外幣兌換定期存款（1個月）',
                'source': 'bank',
                'conditions': ['exchange']
            },
            '1w': {
                'rate': float(usd_match.group(2)),
                'min_deposit': 1000,
                'note': '外幣兌換定期存款（1星期）',
                'source': 'bank',
                'conditions': ['exchange']
            }
        }
    
    # Parse CNY rates
    cny_match = re.search(r'人民幣[\s\t]+(\d+\.\d+)%[\s\t]+(\d+\.\d+)%', section)
    if cny_match:
        rates['cny'] = {
            '1m': {
                'rate': float(cny_match.group(1)),
                'min_deposit': 10000,
                'note': '外幣兌換定期存款（1個月）',
                'source': 'bank',
                'conditions': ['exchange']
            },
            '1w': {
                'rate': float(cny_match.group(2)),
                'min_deposit': 10000,
                'note': '外幣兌換定期存款（1星期）',
                'source': 'bank',
                'conditions': ['exchange']
            }
        }
    
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