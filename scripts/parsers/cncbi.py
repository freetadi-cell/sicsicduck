"""中信銀行（國際）CNCBI - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Since the official website is blocked (Access Denied), we use HKET as the primary source.

Last update: 2026-07-10 from HKET
"""
import re


def parse(text, tables=None, html=None):
    """Parse CNCBI time deposit rates from HKET article.
    
    Expected format from HKET:
    - 全新客戶: 6個月 3.30% (100萬-200萬)
    - 現有客戶新資金: 12個月 2.95%
    - 現有資金: 12個月 2.90%
    """
    if not text:
        return None
    
    rates = {}
    
    # Parse HKET article text
    lines = text.split('\n')
    
    # Track which section we're in
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Detect section headers
        if '全新客戶' in line and '新資金' in line:
            current_section = 'new_customer'
        elif '現有客戶' in line and '新資金' in line:
            current_section = 'new_funds'
        elif '現有資金' in line:
            current_section = 'existing_funds'
        
        # Extract rates
        if '%' in line:
            # Pattern: 6個月 3.30% or 12個月 2.95%
            # Try to extract period and rate
            period_match = re.search(r'(\d+)個月', line)
            rate_match = re.search(r'(\d+\.?\d*)%', line)
            
            if period_match and rate_match:
                period = f"{period_match.group(1)}m"
                rate = float(rate_match.group(1)) / 100
                
                # Also try to extract deposit amount
                amount_match = re.search(r'(\d+)萬元.*?(\d+)萬元', line)
                min_amount = None
                max_amount = None
                if amount_match:
                    min_amount = int(amount_match.group(1)) * 10000
                    max_amount = int(amount_match.group(2)) * 10000
                
                # Add to appropriate section
                if 'hkd' not in rates:
                    rates['hkd'] = {}
                
                if period not in rates['hkd']:
                    rates['hkd'][period] = {}
                
                if current_section:
                    section_data = {'rate': rate, 'source': 'hket'}
                    if min_amount:
                        section_data['min_deposit'] = min_amount
                    if max_amount:
                        section_data['max_deposit'] = max_amount
                    
                    rates['hkd'][period][current_section] = section_data
    
    if rates:
        rates['note'] = '中信銀行（國際）港元定期存款（來源：HKET）'
        return rates
    return None


def parse_hket_url(url):
    """Fetch and parse CNCBI rates from HKET article URL.
    
    This is a convenience function for the scraper to use.
    """
    # The scraper should use web_fetch to get the article content
    # and then pass it to parse()
    pass
