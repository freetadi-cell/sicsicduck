"""中銀香港 BOCHK - Parser for time deposit promotion rates."""
import re

def parse(text, tables=None):
    """Parse BOCHK new fund time deposit rates.
    
    Key section:
    定期存款期  綜合理財服務  3 個月  6 個月  12 個月  申請渠道
    港元  「私人財富」/「中銀理財」  2.10%  1.90%  -  網上銀行、手機銀行
    美元  「私人財富」/「中銀理財」  3.00%  2.90%  -
    """
    if not text:
        return None
    
    rates = {}
    note = '網上銀行新資金特優定期存款'
    
    # Find the rate table section
    table_idx = text.find('3 個月\t6 個月\t12 個月')
    if table_idx < 0:
        table_idx = text.find('3 个 月\t6 个 月\t12 个 月')
    if table_idx < 0:
        # Try finding just the table structure
        table_idx = text.find('定期存款期')
    
    if table_idx < 0:
        return None
    
    section = text[table_idx:table_idx+1000]
    
    # Extract HKD rates (first row after 港元)
    # Pattern: 港元  ...  2.10%  1.90%  -
    hkd_match = re.search(r'港元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if hkd_match:
        rates['hkd'] = {'3m': float(hkd_match.group(1)), '6m': float(hkd_match.group(2))}
        # Check for 12 month
        hkd_12 = re.search(r'港元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if hkd_12:
            rates['hkd']['12m'] = float(hkd_12.group(3))
    
    # USD rates
    usd_match = re.search(r'美元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%', section)
    if usd_match:
        rates['usd'] = {'3m': float(usd_match.group(1)), '6m': float(usd_match.group(2))}
        usd_12 = re.search(r'美元\s+[^\d]*?(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%', section)
        if usd_12:
            rates['usd']['12m'] = float(usd_12.group(3))
    
    if rates:
        rates['note'] = note
        return rates
    return None
