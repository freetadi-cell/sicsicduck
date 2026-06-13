"""集友銀行 Chiyu Bank - Parser for time deposit rates.

The bank's promotional rates are in a PDF linked from the deposit page.
We download the page HTML, find the first PDF link, download it, and
extract rates using pdftotext.

Priority: 新資金定期存款 (higher tier) > 特優定期存款 (higher tier)
"""
import re
import subprocess
import tempfile
import os


def parse(text, tables=None, html=None):
    """Parse Chiyu Bank time deposit rates from PDF."""
    try:
        # Download the deposit page HTML
        r = subprocess.run(
            ['curl', '-sL', '--max-time', '15',
             'https://www.chiyubank.com/cyb/index/zxxx/20230523/index.shtml'],
            capture_output=True, timeout=20
        )
        html = r.stdout.decode('utf-8', errors='ignore')

        # Find first PDF link
        pdf_match = re.search(r'href=["\'](/cyb/attachDir/[^"\']*\.pdf)["\']', html)
        if not pdf_match:
            return None

        pdf_url = f"https://www.chiyubank.com{pdf_match.group(1)}"

        # Download PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        r = subprocess.run(
            ['curl', '-sL', '--max-time', '15', '-o', tmp_path, pdf_url],
            capture_output=True, timeout=20
        )
        if r.returncode != 0:
            return None

        # Extract text from PDF
        r = subprocess.run(
            ['pdftotext', '-layout', tmp_path, '-'],
            capture_output=True, text=True, timeout=10
        )
        os.unlink(tmp_path)

        if r.returncode != 0:
            return None

        return _parse_pdf_text(r.stdout)

    except Exception:
        return None


def _parse_pdf_text(pdf_text):
    """Extract rates from the PDF text content.

    PDF structure (2026 format):
    1. 港元新資金定期存款推廣 — 只適用於分行
       Two tiers: 100萬-5000萬 (higher) | 20萬-100萬 (lower)
       Periods: 1m 3m 4m 6m 12m
       Rates line: 5 lower + 5 higher = 10 rates

    2. 美元新資金定期存款推廣 — 只適用於分行
       Two tiers: 3萬-12.5萬 (lower) | 12.5萬-1000萬 (higher)
       Periods: 1m 3m 4m 6m 12m

    3. 港元／美元／人民幣特優定期存款推廣 — 分行/網上/手機銀行
       HKD: two tiers (10 rates)
       USD: two tiers (10 rates)
       RMB: one tier (5 rates)
    """
    if not pdf_text:
        return None

    rates = {}

    # Parse 港元新資金定期存款推廣
    hkd_rates = _parse_new_funds_section(pdf_text, '港元新資金定期存款推廣')
    if hkd_rates:
        rates['hkd'] = hkd_rates

    # Parse 美元新資金定期存款推廣
    usd_rates = _parse_new_funds_section(pdf_text, '美元新資金定期存款推廣')
    if usd_rates:
        rates['usd'] = usd_rates

    # Parse 人民幣 from 特優定期存款推廣 section
    cny_rates = _parse_cny_section(pdf_text)
    if cny_rates:
        rates['cny'] = cny_rates

    if not rates:
        # Fallback: try 特優定期存款
        return _parse_special_rates(pdf_text)

    rates['note'] = '新資金定期存款推廣（分行）'
    return rates


def _parse_cny_section(text):
    """Parse 人民幣 rates from the 特優定期存款推廣 section.
    
    Format in PDF:
                                 人民幣
    存款金額                      人民幣 20萬元至1000萬元
    存 款 期     1個月         3個月       4個月       6個月             12個月
    年 利 率    0.80%       1.35%        1.35%       1.35%       1.35%
    """
    # Find the 人民幣 subsection within 特優定期存款推廣
    special_idx = text.find('特優定期存款推廣')
    if special_idx < 0:
        return None
    
    special_section = text[special_idx:]
    
    # Find 人民幣 within this section
    rmb_idx = special_section.find('人民幣')
    if rmb_idx < 0:
        return None
    
    rmb_section = special_section[rmb_idx:]
    
    # Find the rates line (5 percentages)
    lines = rmb_section.split('\n')
    for line in lines[:10]:  # Only look at first 10 lines
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) == 5:
            periods = ['1m', '3m', '4m', '6m', '12m']
            result = {}
            for i, period in enumerate(periods):
                result[period] = float(pcts[i])
            return result
    
    return None


def _parse_new_funds_section(text, section_name):
    """Parse a 新資金 section for a given currency.

    Layout: section header, then '新資金' label, two tier labels on one line,
    period headers, then rates line with 10 percentages (5 lower + 5 higher).
    """
    idx = text.find(section_name)
    if idx < 0:
        return None

    section = text[idx:idx + 600]  # limit search window

    lines = section.split('\n')
    for line in lines:
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) == 10:
            # First 5 = 20萬-100萬 (lower), last 5 = 100萬-5000萬 (higher)
            # Take the MAX of both tiers for each period
            periods = ['1m', '3m', '4m', '6m', '12m']
            result = {}
            for i, period in enumerate(periods):
                result[period] = max(float(pcts[i]), float(pcts[5 + i]))
            return result

    return None


def _parse_special_rates(text):
    """Fallback: parse 特優定期存款推廣 section."""
    marker = '特優定期存款推廣'
    idx = text.find(marker)
    if idx < 0:
        return None

    section = text[idx:]

    rates = {}

    hkd_start = section.find('港元')
    usd_start = section.find('美元', hkd_start + 2 if hkd_start >= 0 else 0)
    rmb_start = section.find('人民幣', usd_start + 2 if usd_start >= 0 else 0)

    if hkd_start >= 0:
        end = usd_start if usd_start > hkd_start else len(section)
        block = section[hkd_start:end]
        parsed = _parse_block_10(block)
        if parsed:
            rates['hkd'] = parsed

    if usd_start >= 0:
        end = rmb_start if rmb_start > usd_start else len(section)
        block = section[usd_start:end]
        parsed = _parse_block_10(block)
        if parsed:
            rates['usd'] = parsed

    if rates:
        rates['note'] = '特優定期存款推廣（分行/網上/手機銀行）'
        return rates
    return None


def _parse_block_10(block):
    """Parse a block with 10 percentages (5 lower + 5 higher)."""
    lines = block.split('\n')
    for line in lines:
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) == 10:
            periods = ['1m', '3m', '4m', '6m', '12m']
            result = {}
            for i, period in enumerate(periods):
                result[period] = float(pcts[5 + i])
            return result
    return None
