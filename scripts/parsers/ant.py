"""螞蟻銀行 Ant Bank - Parser for time deposit rates.

Data source: HKET (香港經濟日報）
URL pattern: https://wealth.hket.com/article/XXXXXXX

Note: 官網 404 錯誤，使用 HKET 作為主要數據源。

Parser 設計：
- 使用 hket_common 通用解析器
- 不依賴固定的新聞 ID 或標題
- 自動識別存款期限和利率
- 支援多種利率格式
"""
from parsers.hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse Ant Bank time deposit rates from HKET article.
    
    支援的利率格式：
    - 新資金：1月 1.5%, 3月 1.8%, 6月 2.2%, 9月 2.3%, 12月 2.5%
    - 起存額：10萬元
    """
    if not text:
        return None
    
    # 使用通用 HKET 解析器
    result = parse_hket_article(text, bank_name='螞蟻銀行')
    
    return result