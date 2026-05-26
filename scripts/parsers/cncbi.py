"""中信銀行（國際）CNCBI - Parser for time deposit rates."""
import re

def parse(text, tables=None):
    """Parse CNCBI time deposit rates.
    
    Page shows:
    定期存款利率 - 港元
    通知存款  一星期  二星期  一個月  二個月  三個月  六個月  十二個月
    0.0010   0.0010  0.0010  0.0100  0.0100  0.0100  0.0500  0.1500
    """
    if not text:
        return None
    
    rates = {}
    note = '定期存款利率'
    
    # Find 定期存款利率 - 港元 section
    hkd_section = text[text.find('定期存款利率 - 港元'):] if '定期存款利率 - 港元' in text else ''
    if hkd_section:
        # Look for rate numbers after the headers
        nums = re.findall(r'(\d+\.\d{4})', hkd_section[:200])
        if len(nums) >= 8:
            rates['hkd'] = {
                '1m': float(nums[3]),
                '3m': float(nums[5]),
                '6m': float(nums[6]),
                '12m': float(nums[7]),
            }
    
    # USD section
    usd_section = text[text.find('定期存款利率 - 美元'):] if '定期存款利率 - 美元' in text else ''
    if usd_section:
        nums = re.findall(r'(\d+\.\d{4})', usd_section[:200])
        if len(nums) >= 8:
            rates['usd'] = {
                '1m': float(nums[3]),
                '3m': float(nums[5]),
                '6m': float(nums[6]),
                '12m': float(nums[7]),
            }
    
    if rates:
        rates['note'] = note
        return rates
    return None
