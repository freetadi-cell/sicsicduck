"""象象銀行 EleBank (Airstar) - Parser for time deposit rates.

Page: https://www.elebank.com/zh-hk/hkprime.html
HKD rates shown by default. USD rates shown after clicking "美元" tab.
"""
import re


def parse(text, tables=None):
    """Parse EleBank (象象銀行) time deposit rates.

    Detects currency from the heading:
      定期存款利率（港幣）→ HKD
      定期存款利率（美元）→ USD
    """
    if not text:
        return None

    td_idx = text.find('定期存款利率')
    if td_idx < 0:
        return None

    section = text[td_idx:td_idx + 1000]

    # Detect currency from heading
    heading_end = section.find('\n')
    heading = section[:heading_end] if heading_end > 0 else section[:50]
    is_usd = '美元' in heading
    currency = 'usd' if is_usd else 'hkd'

    # Find the period header row and rate data row
    deposit_idx = section.find('存款期')
    if deposit_idx < 0:
        return None

    # 利率 in the data row appears AFTER 存款期
    rate_row_idx = section.find('利率', deposit_idx + 3)
    if rate_row_idx < 0:
        return None

    # Header row is from 存款期 to just before 利率 row
    header = section[deposit_idx:rate_row_idx]
    rate_section = section[rate_row_idx:]
    row_rates = re.findall(r'(\d+\.\d+)%', rate_section)

    if not row_rates:
        return None

    period_labels = ['1 星期', '1 個月', '2 個月', '3 個月', '4 個月', '6 個月', '9 個月', '12 個月']
    label_to_key = {
        '1 星期': '1w', '1 個月': '1m', '2 個月': '2m', '3 個月': '3m',
        '4 個月': '4m', '6 個月': '6m', '9 個月': '9m', '12 個月': '12m',
    }
    periods_in_order = []
    for label in period_labels:
        if label in header:
            periods_in_order.append(label)

    # Map rates to periods
    rates = {}
    for i, label in enumerate(periods_in_order):
        if i < len(row_rates):
            key = label_to_key[label]
            rates[key] = float(row_rates[i])

    if not rates:
        return None

    return {currency: rates, 'note': '定期存款年利率'}
