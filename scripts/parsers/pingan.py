"""平安數字銀行 PAObank - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Note: 官網被 Cloudflare 阻擋，使用 HKET 作為主要數據源。

Parser 設計：
- 使用 hket_common 通用解析器
- 不依賴固定的新聞 ID 或標題
- 自動識別新客戶推廣利率
- 支援多種利率格式
"""
from .hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse PAObank time deposit rates from HKET article.
    
    支援的利率格式：
    - 新客戶 1個月 8.0%（首5萬）
    - 新資金：1月 2.5%, 3月 3.0%, 6月 2.9%, 12月 3.1%
    - 現有資金：1月 2.4%, 3月 3.0%, 6月 2.85%, 12月 3.0%
    """
    if not text:
        return None
    
    # 使用通用 HKET 解析器
    result = parse_hket_article(text, bank_name='平安數字銀行')
    
    return result