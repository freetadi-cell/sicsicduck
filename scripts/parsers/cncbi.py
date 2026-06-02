"""中信銀行（國際）CNCBI - Parser for time deposit rates.

Uses two sources:
1. inMotion promo page (new fund rates) - curl (doesn't need browser)
2. Main rate table page (board rates) - browser scrape fallback
"""
import re
import subprocess
import logging

logger = logging.getLogger(__name__)

PROMO_URL = 'https://www.cncbinternational.com/personal/e-banking/inmotion/tc/offers/time_deposit/index.html'


def _fetch_promo_rates():
    """Try to fetch promo rates via curl (browser is blocked by CNCBI WAF)."""
    try:
        result = subprocess.run(
            ['curl', '-sL', '--max-time', '15', PROMO_URL],
            capture_output=True, timeout=20
        )
        html = result.stdout.decode('utf-8', errors='ignore')
        if 'Access Denied' in html or len(html) < 200:
            return None
        return html
    except Exception as e:
        logger.debug(f"CNCBI promo fetch failed: {e}")
        return None


def parse(text, tables=None, html=None):
    """Parse CNCBI time deposit rates.
    
    First try promo rates from inMotion page (via curl, no browser needed).
    Then fall back to board rates from rate table page (via browser scrape).
    """
    rates = {}
    
    # Try promo rates first (doesn't need browser text)
    promo_html = _fetch_promo_rates()
    if promo_html:
        promo_text = re.sub(r'<[^>]+>', ' ', promo_html)
        promo_text = re.sub(r'\s+', ' ', promo_text)
        
        pcts = re.findall(r'高達\s*(\d+\.\d+)%', promo_text)
        if len(pcts) >= 1:
            rates['hkd'] = {'3m': float(pcts[0])}
            if len(pcts) >= 2:
                rates['usd'] = {'3m': float(pcts[1])}
            rates['note'] = 'inMotion新資金定期存款特惠年利率'
            return rates
    
    # Fallback: board rates from rate table page (needs browser text)
    if not text:
        return None
    
    board_idx = text.find('定期存款利率')
    if board_idx >= 0:
        section = text[board_idx:board_idx + 2000]
        hkd_rates = {}
        for period, label in [('1m', '一個月'), ('3m', '三個月'), ('6m', '六個月'), ('12m', '十二個月')]:
            m = re.search(rf'{label}\s+(\d+\.\d+)%', section)
            if m:
                hkd_rates[period] = float(m.group(1))
        if hkd_rates:
            rates['hkd'] = hkd_rates
            rates['note'] = '定期存款利率'
            return rates
    
    return None
