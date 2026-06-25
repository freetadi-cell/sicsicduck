"""交通銀行 Bank of Communications - Parser for time deposit rates.

Data source: PDF file fetched via API
- POST to /HK/getContentPath.do with fileId to get PDF path
- Download PDF from /hk/uploadhk/{filePath}
- Extract text using pdftotext

Personal customer rates (lowest threshold) are extracted:
- 每日特息定期存款（電子渠道）
- HKD: 20,000 minimum
- USD: 3,000 minimum
- CNY: 10,000 minimum
"""

import subprocess
import json
import re
import os
import tempfile


def parse(text, tables=None, html=None):
    """
    Parse BOCOM rates from PDF text.
    
    The PDF contains multiple rate tables:
    1. 網上定期存款 (online time deposit) - higher rates, higher thresholds
    2. 每日特息定期存款 (daily preferential) - lower thresholds, what we want
    
    We extract the "每日特息定期存款" rates for personal customers via e-channel.
    
    PDF structure:
    - Each row has: 貨幣 | 港元 | 美元 | 人民幣
    - Under each currency: 起存金額 | 1個月 | 3個月 | 6個月 | 12個月
    - Split into 電子渠道 (e-channel) and 本行網點 (branch)
    - Each section has 個人客戶 (personal) and 公司客戶 (corporate)
    
    Strategy:
    1. Find "每日特息定期存款" section
    2. Find "電子渠道" sub-section (higher rates than branch)
    3. Find "個人客戶" row
    4. Parse the 3 currencies row-by-row
    """
    if not text:
        return None
    
    hkd = {}
    usd = {}
    cny = {}
    
    # Find "每日特息定期存款" section
    daily_idx = text.find('每日特息定期存款')
    if daily_idx < 0:
        daily_idx = text.find('Daily Preferential')
    
    if daily_idx < 0:
        return None
    
    section = text[daily_idx:daily_idx + 4000]
    
    # Find "電子渠道" subsection (before "本行網點")
    echannel_idx = section.find('電子渠道')
    branch_idx = section.find('本行網點')
    
    if echannel_idx >= 0:
        if branch_idx >= 0 and branch_idx > echannel_idx:
            echannel_section = section[echannel_idx:branch_idx]
        else:
            echannel_section = section[echannel_idx:echannel_idx + 2000]
    else:
        echannel_section = section
    
    # Find "個人客戶" in e-channel section
    personal_idx = echannel_section.find('個人客戶')
    if personal_idx >= 0:
        personal_section = echannel_section[personal_idx:personal_idx + 800]
        
        # Extract rates row by row, looking for period markers
        # Pattern: "N 個月" followed by percentages
        
        # Period patterns (with and without spaces)
        period_patterns = [
            ('1m', ['1 個月', '1個月']),
            ('3m', ['3 個月', '3個月']),
            ('6m', ['6 個月', '6個月']),
            ('12m', ['12 個 月', '12個月', '12 個月']),
        ]
        
        for period_key, patterns in period_patterns:
            period_idx = -1
            for p in patterns:
                period_idx = personal_section.find(p)
                if period_idx >= 0:
                    break
            
            if period_idx >= 0 and period_idx < 500:
                # Get the row text after the period marker
                row_text = personal_section[period_idx:period_idx + 100]
                
                # Fix space in decimals like "2. 75%" -> "2.75%"
                row_text_clean = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', row_text)
                
                # Extract all percentages in this row
                percentages = re.findall(r'(\d+\.\d+|\d+)%', row_text_clean)
                
                if len(percentages) >= 3:
                    # First % is HKD, second is USD, third is CNY (personal)
                    # Fourth % is HKD, fifth is USD, sixth is CNY (corporate)
                    hkd[period_key] = float(percentages[0])
                    usd[period_key] = float(percentages[1])
                    cny[period_key] = float(percentages[2])
    
    result = {}
    if hkd:
        result['hkd'] = hkd
    if usd:
        result['usd'] = usd
    if cny:
        result['cny'] = cny
    
    if result:
        result['note'] = '每日特息定期存款（電子渠道）'
        return result
    return None


def fetch_pdf_text(file_id='2600167'):
    """
    Fetch BOCOM rates PDF and extract text.
    
    Steps:
    1. POST to API to get PDF path
    2. Download PDF
    3. Extract text using pdftotext
    
    Returns: (text, None, None) tuple for compatibility with scrape_page()
    """
    import urllib.request
    import urllib.parse
    
    base_url = 'https://www.hk.bankcomm.com'
    
    # Step 1: Get PDF path from API
    api_url = f'{base_url}/HK/getContentPath.do'
    req_body = {
        'REQ_HEAD': {'TRAN_PROCESS': '', 'TRAN_ID': ''},
        'REQ_BODY': {'fileId': file_id}
    }
    data = f"REQ_MESSAGE={json.dumps(req_body)}".encode('utf-8')
    
    try:
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            api_result = json.loads(resp.read().decode('utf-8'))
        
        if api_result.get('RSP_HEAD', {}).get('TRAN_SUCCESS') != '1':
            return None, None, None
        
        file_path = api_result['RSP_BODY']['filePath']
        file_name = api_result['RSP_BODY']['fileName']
        
    except Exception as e:
        print(f"BOCOM API error: {e}")
        return None, None, None
    
    # Step 2: Download PDF
    pdf_url = f"{base_url}/hk/uploadhk/{file_path}"
    pdf_path = None
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
            req = urllib.request.Request(
                pdf_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                tmp.write(resp.read())
    except Exception as e:
        print(f"BOCOM PDF download error: {e}")
        return None, None, None
    
    # Step 3: Extract text using pdftotext
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=10
        )
        text = result.stdout
    except Exception as e:
        print(f"pdftotext error: {e}")
        text = None
    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)
    
    return text, None, None


# For testing
if __name__ == '__main__':
    text, _, _ = fetch_pdf_text()
    if text:
        print("=== PDF Text ===")
        print(text[:2000])
        print("\n=== Parsed Rates ===")
        result = parse(text)
        print(json.dumps(result, indent=2, ensure_ascii=False))