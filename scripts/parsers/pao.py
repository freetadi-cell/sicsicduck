"""平安數字銀行 PAO Bank - Parser for time deposit rates.

Supports three data sources:
1. HKET article (wealth.hket.com) - primary source
2. 新資金定期存款優惠頁 (retail-td-newfund.html)
3. 一般定期存款頁 (retail-savings.html)

HKET article format:
存款期  年利率  起存額  條件
1個月  2.5厘  100元  新資金
3個月  3.0厘
6個月  2.9厘
12個月  3.1厘

平安數字銀行現有資金3.0厘年利率
存款期  年利率  起存額  條件
1個月  2.4厘  100元  不論新舊資金
3個月  3.0厘
6個月  2.85厘
12個月  3.0厘
24個月  2.95厘

新資金優惠頁格式:
1 個月港元定期存款：年利率 2.50%
3 個月港元定期存款：年利率 2.90%
"""
import re


def parse(text, tables=None, html=None):
    """Parse PAO Bank (平安數字銀行) time deposit rates.

    Priority:
    1. HKET article text format
    2. Bank website formats
    """
    # Try HKET format first
    if text and ('厘' in text or '%' in text) and ('平安數字' in text or 'PAO' in text):
        result = _parse_hket(text)
        if result:
            return result
    
    # Fallback to bank website formats
    if text:
        result = _parse_bank_website(text)
        if result:
            return result
    
    return None


def _parse_hket(text):
    """Parse HKET article format for PAO Bank.
    
    The article contains multiple rate tables:
    1. 新資金定期存款優惠
    2. 現有資金（不論新舊資金）
    3. 新客戶專享 (8.0厘)
    """
    rates = {}
    
    # Find sections
    new_funds_start = text.find('新資金')
    existing_funds_start = text.find('現有資金') if '現有資金' in text else text.find('不論新舊資金')
    new_customer_start = text.find('新客戶')
    
    hkd = {}
    
    # Parse 新資金 section
    if new_funds_start >= 0:
        section_end = existing_funds_start if existing_funds_start > new_funds_start else len(text)
        section = text[new_funds_start:section_end]
        _parse_rate_section(section, hkd, 'new_funds')
    
    # Parse 現有資金 section
    if existing_funds_start >= 0:
        section_end = len(text)
        section = text[existing_funds_start:section_end]
        _parse_rate_section(section, hkd, 'existing_funds')
    
    # Parse 新客戶專享 (special high rate for limited time)
    if new_customer_start >= 0:
        section = text[new_customer_start:new_customer_start+500]
        m = re.search(r'(\d+\.?\d*)厘', section)
        if m:
            rate = float(m.group(1))
            # Find min deposit
            deposit_match = re.search(r'(\d+)萬', section)
            min_deposit = int(deposit_match.group(1)) * 10000 if deposit_match else 50000
            # Find period
            period_match = re.search(r'(\d+)\s*個月', section)
            period_key = f'{period_match.group(1)}m' if period_match else '1m'
            
            if period_key not in hkd:
                hkd[period_key] = {}
            hkd[period_key]['new_customer'] = {
                'rate': rate,
                'min_deposit': min_deposit,
                'note': '全新客戶首5萬，推廣期有限',
                'source': 'hket',
                'conditions': ['new_customer', 'limited_time']
            }
    
    if hkd:
        rates['hkd'] = hkd
    
    if rates:
        return rates
    return None


def _parse_rate_section(section, hkd, fund_type):
    """Parse a rate section from HKET article."""
    lines = section.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Extract period
        period_match = re.search(r'(\d+)\s*個月', line)
        if not period_match:
            continue
        
        period_num = int(period_match.group(1))
        period_key = f'{period_num}m'
        
        # Extract rate (厘 format)
        rate_match = re.search(r'(\d+\.?\d*)厘', line)
        if not rate_match:
            continue
        
        rate = float(rate_match.group(1))
        
        # Extract min deposit
        min_deposit = 100
        deposit_match = re.search(r'(\d+)元', line)
        if deposit_match:
            min_deposit = int(deposit_match.group(1))
        
        # Build note based on fund type
        if fund_type == 'new_funds':
            note = '新資金定期存款優惠'
            conditions = ['new_funds']
        else:
            note = '不論新舊資金'
            conditions = []
        
        rate_entry = {
            'rate': rate,
            'min_deposit': min_deposit,
            'note': note,
            'source': 'hket',
            'conditions': conditions
        }
        
        if period_key not in hkd:
            hkd[period_key] = {}
        hkd[period_key][fund_type] = rate_entry


def _parse_bank_website(text):
    """Parse bank website format."""
    rates = {}
    
    # === 新資金定期存款優惠 ===
    nf_idx = text.find('新資金定期存款優惠')
    if nf_idx >= 0:
        nf_section = text[nf_idx:nf_idx + 2000]
        hkd_nf = {}

        # Match patterns like "1 個月港元定期存款：年利率 2.50%"
        for period, label in [('1m', '1'), ('3m', '3'), ('6m', '6'), ('12m', '12')]:
            m = re.search(
                rf'{label}\s*個月港元定期存款[：:]\s*年利率\s*(\d+\.\d+)%',
                nf_section
            )
            if m:
                hkd_nf[period] = {
                    'rate': float(m.group(1)),
                    'new_funds': True,
                    'min_deposit': 100,
                    'note': '新資金定期存款優惠',
                    'source': 'bank'
                }

        if hkd_nf:
            rates['hkd'] = hkd_nf

    # === 一般定期存款年利率 ===
    td_idx = text.find('定期存款年利率')
    if td_idx >= 0:
        td_section = text[td_idx:td_idx + 800]
        hkd_std = {}
        usd_std = {}

        for period, label in [('1m', '1個月'), ('3m', '3個月'), ('6m', '6個月'), ('12m', '12個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%\s+\d+\.\d+%\s+(\d+\.\d+)%', td_section)
            if m:
                hkd_std[period] = {
                    'rate': float(m.group(1)),
                    'min_deposit': 1,
                    'note': '定期存款年利率',
                    'source': 'bank'
                }
                usd_std[period] = {
                    'rate': float(m.group(2)),
                    'min_deposit': 1,
                    'note': '定期存款年利率',
                    'source': 'bank'
                }

        if 'hkd' in rates:
            for period, rate_dict in hkd_std.items():
                if period in rates['hkd'] and isinstance(rates['hkd'][period], dict):
                    rates['hkd'][period]['existing_funds'] = rate_dict
        elif hkd_std:
            rates['hkd'] = {}
            for period, rate_dict in hkd_std.items():
                rates['hkd'][period] = {
                    'new_funds': None,
                    'existing_funds': rate_dict,
                    'exchange': None,
                }

        if usd_std:
            rates['usd'] = {}
            for period, rate_dict in usd_std.items():
                rates['usd'][period] = {
                    'new_funds': None,
                    'existing_funds': rate_dict,
                    'exchange': None,
                }

    if rates and ('hkd' in rates or 'usd' in rates):
        return rates
    return None