"""螞蟻銀行 Ant Bank - Parser for time deposit rates.

Page: https://www.antbank.hk/rates?lang=zh_hk

Ant Bank is a virtual bank. The rates page shows:
- 美元定期存款年利率及新資金、大額定存額外一覽
- 港幣定期存款年利率及新資金、大額定存額外一覽

We extract the 總年利率 (total annual rate including new funds bonus).

Table structure (each value on separate line):
1個月
3.00%
0.00%
0.00%
3.00%

Period, base_rate, new_funds_bonus, large_deposit_bonus, total_rate
"""
import re
import json


def parse(text, tables=None, html=None):
    if not text:
        return None

    hkd = {}
    usd = {}

    # Handle escaped newlines from agent-browser eval
    if '\\n' in text:
        text = text.replace('\\n', '\n').replace('\\t', '\t')
    
    # Look for 美元定期存款 section
    usd_idx = text.find('美元定期存款年利率')
    usd_end = text.find('港幣定期存款年利率', usd_idx) if usd_idx >= 0 else -1
    if usd_end < 0:
        usd_end = usd_idx + 2000 if usd_idx >= 0 else 0
    
    if usd_idx >= 0:
        usd_section = text[usd_idx:usd_end]
        
        # Split into lines
        lines = [l.strip() for l in usd_section.split('\n') if l.strip()]
        
        # Find period markers and extract following 4 percentages
        i = 0
        while i < len(lines):
            line = lines[i]
            if line in ['1個月', '3個月', '6個月', '9個月', '12個月']:
                period_map = {'1個月': '1m', '3個月': '3m', '6個月': '6m', '9個月': '9m', '12個月': '12m'}
                period_key = period_map.get(line)
                
                # Next 4 lines should be percentages
                percentages = []
                for j in range(1, 5):
                    if i + j < len(lines):
                        m = re.match(r'(\d+\.\d+)%', lines[i + j])
                        if m:
                            percentages.append(float(m.group(1)))
                
                if len(percentages) >= 4 and period_key:
                    usd[period_key] = percentages[-1]  # Last is 總年利率
            i += 1

    # Look for 港幣定期存款 section
    hkd_idx = text.find('港幣定期存款年利率')
    hkd_end = text.find('網站地圖', hkd_idx) if hkd_idx >= 0 else -1
    if hkd_end < 0:
        hkd_end = hkd_idx + 2500 if hkd_idx >= 0 else 0
    
    if hkd_idx >= 0:
        hkd_section = text[hkd_idx:hkd_end]
        
        lines = [l.strip() for l in hkd_section.split('\n') if l.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            if line in ['1星期', '1個月', '3個月', '6個月', '9個月', '12個月']:
                period_map = {'1星期': '1w', '1個月': '1m', '3個月': '3m', '6個月': '6m', '9個月': '9m', '12個月': '12m'}
                period_key = period_map.get(line)
                
                percentages = []
                for j in range(1, 5):
                    if i + j < len(lines):
                        m = re.match(r'(\d+\.\d+)%', lines[i + j])
                        if m:
                            percentages.append(float(m.group(1)))
                
                if len(percentages) >= 4 and period_key:
                    hkd[period_key] = percentages[-1]
            i += 1

    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd

    if result:
        result['note'] = '總年利率（含新資金加息）'
        return result
    return None


# For testing
if __name__ == '__main__':
    import subprocess
    
    # Test with agent-browser
    subprocess.run(['agent-browser', 'close'], capture_output=True, timeout=5)
    
    result = subprocess.run(
        ['agent-browser', 'open', 'https://www.antbank.hk/rates?lang=zh_hk', '--timeout', '30000'],
        capture_output=True, text=True, timeout=35
    )
    
    import time
    time.sleep(5)
    
    result = subprocess.run(
        ['agent-browser', 'eval', 'document.body.innerText'],
        capture_output=True, text=True, timeout=10
    )
    
    if result.returncode == 0:
        text = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout).strip()
        # Parse JSON if needed
        try:
            text = json.loads(text)
        except:
            pass
        
        print("=== Parsed Rates ===")
        parsed = parse(text)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    
    subprocess.run(['agent-browser', 'close'], capture_output=True, timeout=5)