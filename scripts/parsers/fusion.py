"""富融銀行 Fusion Bank - Parser for time deposit rates.

Data source: HKET (香港經濟日報)
URL pattern: https://wealth.hket.com/article/XXXXXXX

Note: 官網被 EdgeOne 安全防護阻擋，使用 HKET 作為主要數據源。

Parser 設計：
- 使用 hket_common 通用解析器
- 不依賴固定的新聞 ID 或標題
- 自動識別「快閃星期一」等推廣活動
- 支援多種利率格式
"""
from .hket_common import parse_hket_article


def parse(text, tables=None, html=None):
    """Parse Fusion Bank time deposit rates from HKET article.
    
    支援的利率格式：
    - 零元起存：1周 1.0%, 1月 1.6%, 3月 2.7%, 6月 3.0%, 12月 2.9%
    - 快閃星期一：1周 6.88%, 新客1月 25.0%, 12月 3.1%, 美元12月 4.0%
    """
    if not text:
        return None
    
    # 使用通用 HKET 解析器
    result = parse_hket_article(text, bank_name='富融銀行')
    
    return result