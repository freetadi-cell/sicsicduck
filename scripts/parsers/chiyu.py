"""集友銀行 Chiyu Bank - Parser for time deposit rates.

The bank's promotional rates are in a PDF linked from the deposit page.
We download the page HTML, find the first PDF link, download it, and
extract rates using pdftotext.

We use the 特優定期存款 rates (higher tier, 100萬+/12.5萬+) as they
apply to all channels (branch + online + mobile).
"""
import re
import subprocess
import tempfile
import os


def parse(text, tables=None):
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

    The PDF layout for each currency is:
    - Currency header (港元/美元)
    - Two tier descriptions
    - Period headers (same line for both tiers)
    - Rates line: all 10 rates on one line (5 lower tier + 5 higher tier)

    We want the higher tier (last 5 rates in each line).
    """
    if not pdf_text:
        return None

    rates = {}

    # Find 特優定期存款 section
    marker = '特優定期存款推廣'
    idx = pdf_text.find(marker)
    if idx < 0:
        return None

    section = pdf_text[idx:]

    # Parse each currency block
    # HKD block: from "港元" to "美元"
    hkd_start = section.find('港元')
    usd_start = section.find('美元', hkd_start + 2 if hkd_start >= 0 else 0)
    rmb_start = section.find('人民幣', usd_start + 2 if usd_start >= 0 else 0)

    if hkd_start >= 0:
        end = usd_start if usd_start > hkd_start else len(section)
        block = section[hkd_start:end]
        parsed = _parse_currency_block(block)
        if parsed:
            rates['hkd'] = parsed

    if usd_start >= 0:
        end = rmb_start if rmb_start > usd_start else len(section)
        block = section[usd_start:end]
        parsed = _parse_currency_block(block)
        if parsed:
            rates['usd'] = parsed

    if rates:
        rates['note'] = '特優定期存款推廣（分行/網上/手機銀行）'
        return rates
    return None


def _parse_currency_block(block):
    """Parse a single currency block to extract the higher tier rates.

    The rates line contains 10 percentages:
    5 for lower tier + 5 for higher tier.
    We want the higher tier (last 5).
    """
    lines = block.split('\n')
    for line in lines:
        pcts = re.findall(r'(\d+\.\d+)%', line)
        if len(pcts) == 10:
            # Higher tier = last 5
            periods = ['1m', '3m', '4m', '6m', '12m']
            result = {}
            for i, period in enumerate(periods):
                result[period] = float(pcts[5 + i])
            return result
    return None
