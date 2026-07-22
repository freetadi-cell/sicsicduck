"""東亞銀行 BEA - Parser for time deposit rates.

Updated 2026-07-22 to handle the new table format with 新資金/現有資金 rates.

Page: https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html

Table format:
存款期  顯卓私人理財  至尊理財  BEA GOAL
        新資金／現有資金
3個月   2.65 / 2.55   2.60 / 2.55   2.60 / 2.55
6個月   2.65 / 2.55   2.60 / 2.55   2.60 / 2.55
12個月  2.65 / 2.55   2.60 / 2.55   2.60 / 2.55
"""
import re


def parse(text, tables=None, html=None):
    """Parse BEA time deposit rates from promo page.
    
    Returns rates for HKD, USD, CNY with new_funds and existing_funds variants.
    """
    if not text and not tables:
        return None
    
    rates = {}
    
    # Use tables if available (more reliable)
    if tables:
        for table in tables:
            table_str = str(table)
            
            # HKD table (first table with 港元 or no currency specified)
            if '3個月' in table_str and ('顯卓' in table_str or '至尊' in table_str or 'BEA GOAL' in table_str):
                # Check if this is HKD or USD table
                # USD table has higher rates (3.x%)
                if '3.60' in table_str or '3.55' in table_str:
                    # USD table
                    usd_rates = _parse_rate_table(table_str)
                    if usd_rates:
                        rates['usd'] = usd_rates
                        rates['usd']['note'] = '美元新資金定期存款'
                elif '1.40' in table_str or '1.45' in table_str:
                    # CNY table
                    cny_rates = _parse_rate_table(table_str)
                    if cny_rates:
                        rates['cny'] = cny_rates
                        rates['cny']['note'] = '人民幣新資金定期存款'
                else:
                    # HKD table
                    hkd_rates = _parse_rate_table(table_str)
                    if hkd_rates:
                        rates['hkd'] = hkd_rates
                        rates['hkd']['note'] = '港元新資金定期存款'
    
    # Fallback to text parsing
    if not rates and text:
        # Try to extract from text
        for period, label in [('3m', r'3個月'), ('6m', r'6個月'), ('12m', r'12個月')]:
            # Pattern: 3個月  2.65 / 2.55  2.60 / 2.55  2.60 / 2.55
            m = re.search(rf'{label}\s+(\d+\.\d+)\s*/\s*(\d+\.\d+)', text)
            if m:
                if 'hkd' not in rates:
                    rates['hkd'] = {}
                rates['hkd'][period] = {
                    'new_funds': float(m.group(1)),
                    'existing_funds': float(m.group(2))
                }
    
    if rates:
        rates['note'] = '東亞銀行特惠定期存款利率'
        return rates
    return None


def _parse_rate_table(table_str):
    """Parse a single rate table, returning dict of period -> rate (new_funds)."""
    rates = {}
    
    for period, label in [('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
        # Find the line with this period
        lines = table_str.split('\n')
        for line in lines:
            if label in line and '/' in line:
                # Extract first rate (new funds rate)
                # Format: 3個月  2.65 / 2.55  2.60 / 2.55 ...
                m = re.search(r'(\d+\.\d+)\s*/\s*(\d+\.\d+)', line)
                if m:
                    rates[period] = float(m.group(1))  # new funds rate
                    break
    
    return rates if rates else None
