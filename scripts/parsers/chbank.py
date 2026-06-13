"""創興銀行 Chong Hing Bank - Parser for 雲利率 (cloud rates).

Rates are loaded from XML: https://www.chbank.com/xml_rates2/bw_fd_int.xml
"""
import re
import subprocess
import xml.etree.ElementTree as ET

XML_URL = 'https://www.chbank.com/xml_rates2/bw_fd_int.xml'


def parse(text, tables=None, html=None):
    """Parse Chong Hing Bank 雲利率 from XML source."""
    try:
        # Download the XML directly
        result = subprocess.run(
            ['curl', '-sL', '--max-time', '15', XML_URL],
            capture_output=True, timeout=20
        )
        xml_content = result.stdout.decode('utf-8', errors='ignore')
        if not xml_content or '<root>' not in xml_content:
            return None
        
        return _parse_xml(xml_content)
    except Exception:
        return None


def _parse_xml(xml_content):
    """Parse the XML and extract rates for HKD, USD, and RMB."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None
    
    rates = {}
    
    # Parse date
    date_elem = root.find('date')
    if date_elem is not None:
        year = date_elem.findtext('year', '')
        month = date_elem.findtext('month', '').zfill(2)
        day = date_elem.findtext('day', '').zfill(2)
        rates['date'] = f'{year}-{month}-{day}'
    
    # Period mapping
    period_map = {
        'sevenday': '1w',
        'fourteenday': '2w',
        'onemonth': '1m',
        'twomonth': '2m',
        'threemonth': '3m',
        'sixmonth': '6m',
        'ninemonth': '9m',
        'oneyear': '12m',
    }
    
    # Parse each currency
    for currency in root.findall('currency'):
        name = currency.get('name')
        if name not in ['HKD', 'USD', 'RMB']:
            continue
        
        curr_key = 'cny' if name == 'RMB' else name.lower()
        curr_rates = {}
        
        # Get the highest tier (last unit element)
        units = currency.findall('unit')
        if not units:
            continue
        
        # Take the last unit (highest tier: >= 500,000 for HKD, >= 50,000 for others)
        last_unit = units[-1]
        tenor = last_unit.find('tenor')
        if tenor is None:
            continue
        
        for period_elem in tenor:
            pk = period_map.get(period_elem.tag)
            if pk:
                rate_str = period_elem.text
                if rate_str:
                    try:
                        rate = float(rate_str)
                        if rate > 0:
                            curr_rates[pk] = rate
                    except ValueError:
                        pass
        
        if curr_rates:
            rates[curr_key] = curr_rates
    
    if rates:
        rates['note'] = '雲利率（網上/流動理財）'
        return rates
    return None
