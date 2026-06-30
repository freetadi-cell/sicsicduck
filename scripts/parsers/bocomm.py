"""交通銀行 Bank of Communications - Parser for time deposit rates.

Data source: PDF file fetched via API
- POST to /HK/getContentPath.do with fileId to get PDF path
- Download PDF from /hk/uploadhk/{filePath}
- Extract images from PDF (scanned image PDF)
- Use OCR to extract text

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
    Parse BOCOM rates from OCR'd PDF text.
    
    The PDF contains multiple rate tables:
    1. 網上定期存款 (online time deposit) - higher rates, higher thresholds
    2. 每日特息定期存款 (daily preferential) - lower thresholds, what we want
    
    We extract the "每日特息定期存款" rates for personal customers via e-channel.
    
    Strategy:
    1. Find "每日特息定期存款" section
    2. Find "電子渠道" sub-section (higher rates than branch)
    3. Find "個人客戶" row
    4. Parse the 3 currencies (港元, 美元, 人民幣) row-by-row
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
            daily_idx = text.find('特息定期')
    
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
        
        period_patterns = [
            ('1m', ['1 個月', '1個月', '1个月', '1個 月']),
            ('3m', ['3 個月', '3個月', '3个月', '3個 月']),
            ('6m', ['6 個月', '6個月', '6个月', '6個 月']),
            ('12m', ['12 個 月', '12個月', '12 個月', '12个月', '12 個月', '12個 月']),
        ]
        
        for period_key, patterns in period_patterns:
            period_idx = -1
            for p in patterns:
                period_idx = personal_section.find(p)
                if period_idx >= 0:
                    break
            
            if period_idx >= 0 and period_idx < 600:
                # Get the row text after the period marker
                row_text = personal_section[period_idx:period_idx + 150]
                
                # Fix OCR artifacts: "2. 75%" -> "2.75%", "12 個 月" -> "12個月"
                row_text_clean = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', row_text)
                row_text_clean = re.sub(r'(\d+)\s+個\s+月', r'\1個月', row_text_clean)
                row_text_clean = re.sub(r'(\d+)\s+個月', r'\1個月', row_text_clean)
                # Fix percentage with space: "2.60 %" -> "2.60%"
                row_text_clean = re.sub(r'(\d+\.?\d*)\s+%', r'\1%', row_text_clean)
                
                # Extract all percentages in this row
                percentages = re.findall(r'(\d+\.\d+|\d+)%', row_text_clean)
                
                if len(percentages) >= 3:
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
    Fetch BOCOM rates PDF and extract text using OCR.
    
    Steps:
    1. POST to API to get PDF path
    2. Download PDF
    3. Try pdftotext first (for normal PDFs)
    4. If empty, extract images from PDF (scanned image PDF)
    5. Use tesseract OCR to extract text from images
    
    Returns: (text, None, None) tuple for compatibility with scrape_page()
    """
    import urllib.request
    import shutil
    
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
            print(f"BOCOM API error: TRAN_SUCCESS != 1")
            return None, None, None
        
        file_path = api_result['RSP_BODY']['filePath']
        
    except Exception as e:
        print(f"BOCOM API error: {e}")
        return None, None, None
    
    # Step 2: Download PDF
    pdf_url = f"{base_url}/hk/uploadhk/{file_path}"
    pdf_path = None
    img_dir = None
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
            req = urllib.request.Request(
                pdf_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                tmp.write(resp.read())
        print(f"Downloaded PDF: {os.path.getsize(pdf_path)} bytes")
    except Exception as e:
        print(f"BOCOM PDF download error: {e}")
        return None, None, None
    
    # Step 3: Try pdftotext first
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=10
        )
        text = result.stdout.strip()
        if text and len(text) > 100:
            print(f"pdftotext extracted {len(text)} chars")
            return text, None, None
    except Exception as e:
        print(f"pdftotext error: {e}")
    
    # Step 4: Extract images from PDF
    try:
        img_dir = tempfile.mkdtemp(prefix='bocomm_img_')
        img_prefix = os.path.join(img_dir, 'page')
        
        result = subprocess.run(
            ['pdfimages', '-j', pdf_path, img_prefix],
            capture_output=True,
            timeout=10
        )
        
        images = sorted([f for f in os.listdir(img_dir) if f.endswith('.jpg')])
        
        if not images:
            print("No images extracted from PDF")
            return None, None, None
        
        print(f"Extracted {len(images)} images from PDF")
        
        # Step 5: OCR each image
        all_text = []
        for img_file in images:
            img_path = os.path.join(img_dir, img_file)
            
            # Try tesseract directly
            try:
                result = subprocess.run(
                    ['tesseract', img_path, 'stdout', '-l', 'chi_sim+eng', '--psm', '6'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.stdout.strip():
                    all_text.append(result.stdout)
                    print(f"OCR'd {img_file}: {len(result.stdout)} chars")
            except Exception as e:
                print(f"tesseract error for {img_file}: {e}")
        
        if all_text:
            combined_text = '\n\n'.join(all_text)
            print(f"Total OCR text: {len(combined_text)} chars")
            return combined_text, None, None
        
        print("OCR produced no text")
        return None, None, None
        
    except Exception as e:
        print(f"Image extraction/OCR error: {e}")
        return None, None, None
    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)
        if img_dir and os.path.exists(img_dir):
            shutil.rmtree(img_dir)


# For testing
if __name__ == '__main__':
    text, _, _ = fetch_pdf_text()
    if text:
        print("=== PDF Text ===")
        print(text[:2000])
        print("\n=== Parsed Rates ===")
        result = parse(text)
        print(json.dumps(result, indent=2, ensure_ascii=False))