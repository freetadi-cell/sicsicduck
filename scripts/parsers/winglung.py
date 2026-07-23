"""招商永隆 Wing Lung Bank - Parser for time deposit rates.

Updated 2026-07-22 to handle dynamically loaded tables with multi-line format.

Page: https://www.cmbwinglungbank.com/wlb_corporate/hk/personal/investments/financial-information/interest-rates/deposit-interest-rates.html

Note: This page loads data dynamically. The scraper needs to wait 8+ seconds 
for the tables to appear.

Table format (multi-line):
1 個月  分行
        「招商永隆銀行手機App」  0.25000
                                2.00000  0.30000
                                2.10000

The rates are spread across multiple lines. We need to collect all numbers
after each period label and take the last one (highest tier 手機App rate).
"""
import re


def parse(text, tables=None, html=None):
    """Parse Wing Lung Bank time deposit rates.
    
    Expects tables to be provided (from Playwright with long wait).
    """
    if not tables:
        return _parse_text(text)
    
    rates = {}
    
    # Find HKD table
    hkd_rates = _parse_currency_table(tables, '港元定期存款利率')
    if hkd_rates:
        rates['hkd'] = hkd_rates
    
    # Find USD table
    usd_rates = _parse_currency_table(tables, '美元定期存款利率')
    if usd_rates:
        rates['usd'] = usd_rates
    
    # Find CNY table
    cny_rates = _parse_currency_table(tables, '人民幣定期存款利率')
    if cny_rates:
        rates['cny'] = cny_rates
    
    if rates:
        return rates
    return None


def _parse_currency_table(tables, table_marker):
    """Parse rates from a specific currency table.
    
    The table has multi-line format where rates are on different lines
    after the period label. We collect all numbers after each period
    and take the last one (highest tier 手機App rate).
    """
    rates = {}
    
    for table in tables:
        table_str = str(table)
        if table_marker in table_str:
            # Split into lines
            lines = table_str.split('\n')
            
            # Collect all numbers for each period
            current_period = None
            period_numbers = {'1m': [], '3m': [], '6m': [], '12m': []}
            
            for line in lines:
                # Check if this line has a period label
                if '1 個月' in line:
                    current_period = '1m'
                elif '3 個月' in line:
                    current_period = '3m'
                elif '6 個月' in line:
                    current_period = '6m'
                elif '12 個月' in line:
                    current_period = '12m'
                
                # Collect numbers from this line
                if current_period:
                    nums = re.findall(r'(\d+\.\d+)', line)
                    for num in nums:
                        val = float(num)
                        if val > 0.1:  # Filter out very small numbers
                            period_numbers[current_period].append(val)
            
            # For each period, take the last number (highest tier 手機App rate)
            for period_key, numbers in period_numbers.items():
                if numbers:
                    # Take the last number >= 1.0 (手機App rate)
                    for num in reversed(numbers):
                        if num >= 1.0:
                            rates[period_key] = {
                                'rate': num,
                                'min_deposit': 50000,
                                'note': '招商永隆銀行手機App優惠定存利率',
                                'source': 'bank'
                            }
                            break
            
            break
    
    return rates if rates else None


def _parse_text(text):
    """Fallback text parsing (less reliable)."""
    if not text:
        return None
    
    rates = {}
    
    # Try to extract from text
    for period, label in [('1m', '1 個月'), ('3m', '3 個月'), 
                           ('6m', '6 個月'), ('12m', '12 個月')]:
        idx = text.find(label)
        if idx >= 0:
            section = text[idx:idx+300]
            nums = re.findall(r'(\d+\.\d+)', section)
            if nums:
                for num in reversed(nums):
                    rate = float(num)
                    if rate >= 1.0:
                        rates[period] = {
                            'rate': rate,
                            'min_deposit': 50000,
                            'note': '招商永隆銀行手機App優惠定存利率',
                            'source': 'bank'
                        }
                        break
    
    if rates:
        return {'hkd': rates}
    return None