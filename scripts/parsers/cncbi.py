"""中信銀行（國際）CNCBI - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Note: 官網被 Access Denied 阻擋，使用 HKET 作為主要數據源。

Parser 設計：
- 使用 hket_common 通用解析器
- 不依賴固定的新聞 ID 或標題
- 自動識別銀行名稱和利率格式
- 支援 % 和 厘 兩種利率表示方式
"""
from .hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse CNCBI time deposit rates from HKET article.
    
    支援的利率格式：
    - 全新客戶 6個月 3.30%（100萬-200萬）
    - 現有客戶新資金 12個月 2.95厘
    - 現有資金 12個月 2.90%
    """
    if not text:
        return None
    
    # 使用通用 HKET 解析器
    result = parse_hket_article(text, bank_name='中信銀行（國際）')
    
    return result