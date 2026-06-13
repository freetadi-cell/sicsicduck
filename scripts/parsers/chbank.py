"""創興銀行 Chong Hing Bank - Parser for 雲利率 (e-rate / cloud rates).

Uses browser to click the 雲利率 tab, then extracts rates from the rendered table.
Falls back to XML (牌價) if browser fails.
"""
import re
import subprocess
import logging
import time

logger = logging.getLogger(__name__)

PAGE_URL = 'https://www.chbank.com/tc/personal/banking-services/useful-information/deposit-rates/index.shtml'
XML_URL = 'https://www.chbank.com/xml_rates2/bw_fd_int.xml'


def parse(text=None, tables=None, html=None):
    """Parse Chong Hing Bank 雲利率."""
    result = _parse_via_browser()
    if result:
        return result
    logger.warning('chbank: browser extraction failed, falling back to XML board rates')
    return _parse_xml()


def _parse_via_browser():
    """Use agent-browser to click 雲利率 tab and extract rates."""
    try:
        # Open page
        r = subprocess.run(['agent-browser', 'open', PAGE_URL],
                          capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None

        # Get snapshot to find 雲利率 button ref
        r = subprocess.run(['agent-browser', 'snapshot'],
                          capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return None

        # Find ref: snapshot format is button "雲利率" [ref=e61]
        ref_m = re.search(r'button\s+"雲利率"\s*\[ref=(e\d+)\]', r.stdout)
        if not ref_m:
            logger.warning('chbank: cannot find 雲利率 button ref')
            return None

        ref = '@' + ref_m.group(1)
        r = subprocess.run(['agent-browser', 'click', ref],
                          capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return None

        time.sleep(1)

        # Get snapshot with 雲利率 table data
        r = subprocess.run(['agent-browser', 'snapshot'],
                          capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return None

        return _extract_rates_from_snapshot(r.stdout)

    except Exception as e:
        logger.debug(f'chbank browser parse failed: {e}')
        return None


def _extract_rates_from_snapshot(snapshot):
    """Extract rates from agent-browser snapshot.

    Table rows look like:
    - row "人民幣 500,000 至 50,000,000 ------- 0.3500 0.3500 0.8000 1.0000 1.3500 1.3500 1.2000 1.2000 0.3500"

    Columns: 1天 7天 14天 1個月 2個月 3個月 6個月 9個月 12個月 24個月
    Indices:  0   1    2     3     4     5     6     7      8      9
    """
    if not snapshot:
        return None

    # Find 雲利率 table section
    erate_idx = snapshot.find('定期存款（雲利率）')
    if erate_idx < 0:
        return None

    section = snapshot[erate_idx:]

    period_indices = {
        1: '1w', 2: '2w', 3: '1m', 4: '2m',
        5: '3m', 6: '6m', 7: '9m', 8: '12m',
    }

    rates = {}

    # Best tiers for each currency
    # Find each currency's rates from the first row that matches
    # All tiers have the same rates for 雲利率
    currency_patterns = [
        ('港 元', 'hkd'),
        ('美 元', 'usd'),
        ('人民幣', 'cny'),
    ]

    for cn_label, curr_key in currency_patterns:
        # Match: 港 元 5,000 至 49,999 0.0010 0.0100 ... (10 values)
        # or:    人民幣 5,000 至 49,999 ------- 0.3500 ... (with dashes)
        pattern = re.escape(cn_label) + r'\s+[\d,]+\s+(?:至|或以上)\s+[\d,]*\s*([\d.\-]+(?:\s+[\d.\-]+){9})'
        m = re.search(pattern, section)
        if m:
            values = m.group(1).split()
            curr_rates = {}
            for idx, pk in period_indices.items():
                if idx < len(values):
                    val = values[idx]
                    if val not in ('-------', '---', ''):
                        try:
                            rate = float(val)
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


def _parse_xml():
    """Fallback: parse XML for board rates (牌價)."""
    try:
        import xml.etree.ElementTree as ET

        result = subprocess.run(
            ['curl', '-sL', '--max-time', '15', XML_URL],
            capture_output=True, timeout=20
        )
        xml_content = result.stdout.decode('utf-8', errors='ignore')
        if not xml_content or '<root>' not in xml_content:
            return None

        root = ET.fromstring(xml_content)
        rates = {}

        period_map = {
            'sevenday': '1w', 'fourteenday': '2w',
            'onemonth': '1m', 'twomonth': '2m', 'threemonth': '3m',
            'sixmonth': '6m', 'ninemonth': '9m', 'oneyear': '12m',
        }

        for currency in root.findall('currency'):
            name = currency.get('name')
            if name not in ['HKD', 'USD', 'RMB']:
                continue
            curr_key = 'cny' if name == 'RMB' else name.lower()
            curr_rates = {}
            units = currency.findall('unit')
            if not units:
                continue
            # Take highest tier
            last_unit = units[-1]
            tenor = last_unit.find('tenor')
            if tenor is None:
                continue
            for period_elem in tenor:
                pk = period_map.get(period_elem.tag)
                if pk:
                    try:
                        rate = float(period_elem.text)
                        if rate > 0:
                            curr_rates[pk] = rate
                    except (ValueError, TypeError):
                        pass
            if curr_rates:
                rates[curr_key] = curr_rates

        if rates:
            rates['note'] = '牌價利率（備用）'
            return rates
        return None
    except Exception:
        return None
