"""理慧銀行 Livi Bank - Parser for time deposit rates.

Page: https://www.livibank.com/zh_CN/features/livisave.html

Two tables:
- HKD: 存款期及年利率 (HKD) with tiers (500-5万 / 5万+)
- USD: 存款期及年利率 (USD)
"""
import re


def parse(text, tables=None, html=None):
    if not text:
        return None

    hkd = {}
    usd = {}

    # === HKD 定期 ===
    hkd_idx = text.find('存款期及年利率 (HKD)')
    if hkd_idx < 0:
        hkd_idx = text.find('存款期及年利率（HKD）')
    if hkd_idx < 0:
        hkd_idx = text.find('定期存款')
    
    if hkd_idx >= 0:
        # Find the section with rates
        section = text[hkd_idx:hkd_idx + 2000]
        
        # Look for the 5万+ tier (higher rates)
        # Pattern: 1 个月	0.50%	1.20%  → take 1.20% (5万+)
        # Try table format first
        lines = section.split('\n')
        in_hkd_table = False
        for line in lines:
            line = line.strip()
            if '存款期' in line and ('存入金額' in line or 'HKD' in line):
                in_hkd_table = True
                continue
            if in_hkd_table and ('USD' in line or '人民幣' in line or 'CNY' in line or '美元' in line):
                break
            
            if in_hkd_table:
                # Match: 1 个月	0.50%	1.20%  or  3 个月	1.10%	2.50%
                m = re.match(r'(\d+)\s*个?月\s+[\d.]+%\s+([\d.]+)%', line)
                if not m:
                    # Try single rate format
                    m = re.match(r'(\d+)\s*个?月\s+([\d.]+)%', line)
                if m:
                    period_num = int(m.group(1))
                    rate = float(m.group(2))
                    key = _period_key(period_num)
                    if key:
                        hkd[key] = rate

    # Fallback: regex extraction from HKD section
    if not hkd and hkd_idx >= 0:
        section = text[hkd_idx:hkd_idx + 2000]
        # Find all rate pairs: e.g., "3 个月\t1.10%\t2.50%"
        pairs = re.findall(r'(\d+)\s*个?月\s+[\d.]+%\s+([\d.]+)%', section)
        for period_num, rate in pairs:
            key = _period_key(int(period_num))
            if key:
                hkd[key] = float(rate)
        
        # If no pairs, try single rates
        if not hkd:
            singles = re.findall(r'(\d+)\s*个?月\s+([\d.]+)%', section)
            for period_num, rate in singles:
                key = _period_key(int(period_num))
                if key:
                    hkd[key] = float(rate)

    # === USD 定期 ===
    usd_idx = text.find('存款期及年利率 (USD)')
    if usd_idx < 0:
        usd_idx = text.find('存款期及年利率（USD）')
    if usd_idx < 0:
        usd_idx = text.find('USD)')
    
    if usd_idx >= 0:
        # Limit section to before CNY section
        cny_idx = text.find('存款期及年利率 (CNY)', usd_idx)
        if cny_idx < 0:
            cny_idx = text.find('存款期及年利率（CNY）', usd_idx)
        end = cny_idx if cny_idx > usd_idx else usd_idx + 1500
        section = text[usd_idx:end]
        rates = re.findall(r'(\d+)\s*个?月\s+([\d.]+)%', section)
        for period_num, rate in rates:
            key = _period_key(int(period_num))
            if key:
                usd[key] = float(rate)

    # === CNY (人民幣) 定期 ===
    cny = {}
    cny_idx = text.find('存款期及年利率 (CNY)')
    if cny_idx < 0:
        cny_idx = text.find('存款期及年利率（CNY）')
    if cny_idx < 0:
        cny_idx = text.find('CNY)')
    
    if cny_idx >= 0:
        section = text[cny_idx:cny_idx + 1500]
        rates = re.findall(r'(\d+)\s*个?月\s+([\d.]+)%', section)
        for period_num, rate in rates:
            key = _period_key(int(period_num))
            if key:
                cny[key] = float(rate)

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd
    if cny:
        result['cny'] = cny

    if result:
        result['note'] = '定期存款利率（5萬以上）'
        return result
    return None


def _period_key(months):
    mapping = {
        1: '1m', 2: '2m', 3: '3m', 4: '4m',
        6: '6m', 9: '9m', 12: '12m',
    }
    return mapping.get(months)
