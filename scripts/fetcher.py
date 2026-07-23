"""統一數據抓取模組

支援多種抓取方法：
1. Playwright — 用於官網（JS 渲染頁面）
2. requests — 用於 HKET（簡單 HTTP request）
3. web_fetch — 用於 OpenClaw 環境（直接調用 web_fetch tool）

設計目標：
- 統一管理所有抓取邏輯
- 根據銀行配置選擇最佳抓取方法
- 優雅處理失敗（自動 fallback）
"""
import requests
import logging
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger(__name__)

# 銀行抓取策略配置
BANK_FETCH_STRATEGY = {
    # B類：只用 HKET（官網被 CloudFront/Cloudflare 阻擋）
    'cncbi': ['hket'],
    'fusion': ['hket'],
    'ant': ['hket'],
    
    # C類：官網優先，HKET 作為 backup
    'pao': ['general', 'hket'],
    
    # D類：官網優先（PDF 或特殊處理）
    'chiyu': ['general'],
    'icbc': ['general'],
    'welab': ['general'],
    
    # A類：大部分傳統銀行，只用官網
    'hsbc': ['general'],
    'bochk': ['general'],
    'hangseng': ['general'],
    'sc': ['general'],
    'dbs': ['general'],
    'bea': ['general'],
    'fubon': ['general'],
    'bocomm': ['general'],
    'shacom': ['general'],
    'publicbank': ['general'],
    'winglung': ['general'],
    'chbank': ['general'],
    'airstar': ['general'],
    'za': ['general'],
    'livi': ['general'],
    
    # 默認策略：先試官網，失敗再試 HKET
    'default': ['general', 'hket'],
}

# HKET 請求 headers（模擬真人瀏覽器）
HKET_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
}


def fetch_with_playwright(url: str, timeout: int = 30000) -> Optional[str]:
    """用 Playwright 抓取官網（支援 JS 渲染）
    
    注意：這個函數需要在 update_rates.py 中實際調用 Playwright
    因為 Playwright 需要初始化 browser context
    
    Args:
        url: 目標 URL
        timeout: 超時時間（毫秒）
    
    Returns:
        str: 頁面 HTML 內容，失敗返回 None
    """
    # 這個函數只是一個佔位符
    # 實際的 Playwright 抓取邏輯在 update_rates.py 中
    logger.warning("fetch_with_playwright should be called from update_rates.py with Playwright context")
    return None


def fetch_with_requests(url: str, headers: Optional[Dict] = None, timeout: int = 15) -> Optional[str]:
    """用 requests 抓取 HKET（簡單 HTTP request）
    
    Args:
        url: 目標 URL
        headers: 自定義 headers（默認使用 HKET_HEADERS）
        timeout: 超時時間（秒）
    
    Returns:
        str: 頁面 HTML 內容，失敗返回 None
    """
    if not headers:
        headers = HKET_HEADERS
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            # 檢查是否係 CloudFront 錯誤頁面
            if 'ERROR: The request could not be satisfied' in response.text:
                logger.warning(f"CloudFront blocked: {url}")
                return None
            
            # 檢查是否係 Cloudflare 錯誤頁面
            if 'Just a moment' in response.text or 'Checking your browser' in response.text:
                logger.warning(f"Cloudflare blocked: {url}")
                return None
            
            logger.info(f"Successfully fetched with requests: {url}")
            return response.text
        else:
            logger.warning(f"HTTP {response.status_code} for {url}")
            return None
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return None


def fetch_bank_data(
    bank_key: str,
    urls: Dict[str, str],
    playwright_fetch_func=None
) -> Tuple[Optional[str], Optional[str]]:
    """根據策略抓取銀行數據
    
    Args:
        bank_key: 銀行 key（例如 'cncbi', 'fusion'）
        urls: 銀行 URL 配置 {'general': '...', 'hket': '...'}
        playwright_fetch_func: Playwright 抓取函數（可選）
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (頁面內容, 數據源類型)
        例如：('<html>...', 'hket') 或 (None, None)
    """
    # 獲取銀行的抓取策略
    strategy = BANK_FETCH_STRATEGY.get(bank_key, BANK_FETCH_STRATEGY['default'])
    
    logger.info(f"Fetching {bank_key} with strategy: {strategy}")
    
    for source in strategy:
        if source == 'hket' and 'hket' in urls:
            # 用 requests 抓取 HKET
            text = fetch_with_requests(urls['hket'])
            if text:
                logger.info(f"✅ {bank_key} fetched from HKET")
                return text, 'hket'
            else:
                logger.warning(f"❌ {bank_key} failed to fetch from HKET")
        
        elif source == 'general' and 'general' in urls:
            # 用 Playwright 抓取官網
            if playwright_fetch_func:
                text = playwright_fetch_func(urls['general'])
                if text:
                    logger.info(f"✅ {bank_key} fetched from general")
                    return text, 'general'
                else:
                    logger.warning(f"❌ {bank_key} failed to fetch from general")
            else:
                logger.warning(f"Playwright fetch function not provided for {bank_key}")
    
    logger.error(f"❌ All sources failed for {bank_key}")
    return None, None


def is_valid_content(text: str) -> bool:
    """檢查抓取到嘅內容是否有效
    
    Args:
        text: 頁面內容
    
    Returns:
        bool: 是否有效
    """
    if not text:
        return False
    
    # 檢查是否係錯誤頁面
    error_indicators = [
        'ERROR: The request could not be satisfied',
        'Just a moment',
        'Checking your browser',
        'Access Denied',
        '404 Not Found',
        '503 Service Unavailable',
    ]
    
    for indicator in error_indicators:
        if indicator in text:
            return False
    
    return True


def get_fetch_strategy(bank_key: str) -> List[str]:
    """獲取銀行的抓取策略
    
    Args:
        bank_key: 銀行 key
    
    Returns:
        List[str]: 抓取策略列表（例如 ['hket'] 或 ['general', 'hket']）
    """
    return BANK_FETCH_STRATEGY.get(bank_key, BANK_FETCH_STRATEGY['default'])
