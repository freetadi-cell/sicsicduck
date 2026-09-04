#!/usr/bin/env python3
"""
Fetch Chinese news from NewsData.io + RSS feeds for sicsicduck.com
Incremental mode: keeps old news, deduplicates, removes articles older than 30 days
Expanded sources: HK + TW regions from NewsData.io + RSS feeds (SCMP)
"""

import requests
import json
import feedparser
import hashlib
import html as html_lib
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Hong Kong timezone (UTC+8)
HKT = timezone(timedelta(hours=8))

# API Configuration
API_KEY = "pub_00e12f838504473cab89480d31d35522"
BASE_URL = "https://newsdata.io/api/1/news"

# Paths
SCRIPT_DIR = Path(__file__).parent

# 自家圖片庫主題選圖（共用 build_news_local 嘅 theme_for，唔用新聞來源圖片）
import sys as _sys
if str(SCRIPT_DIR) not in _sys.path:
    _sys.path.insert(0, str(SCRIPT_DIR))
try:
    from build_news_local import theme_for as _theme_for
except Exception:
    _theme_for = None
DATA_DIR = SCRIPT_DIR.parent / "data"
NEWS_FILE = DATA_DIR / "news.json"
CACHE_DIR = SCRIPT_DIR.parent / "articles_cache"

# Settings
MAX_AGE_DAYS = 7  # Remove articles older than this (daily cleanup)
MAX_PER_CATEGORY_NORMAL = 10  # Max articles per category per region for daily cron
MAX_PER_CATEGORY_INITIAL = 50  # Max articles per category per region for initial build

# Categories and regions (removed 'cn' and 'tw' to exclude Simplified Chinese and Taiwan news)
# Categories merged into 2 batches to reduce API calls (8 → 2)
# NewsData.io supports comma-separated categories in a single request
CATEGORY_BATCHES = [
    ['business', 'technology', 'science', 'health'],
    ['sports', 'politics', 'world'],
]
REGIONS = ['hk']

# RSS Feeds - Hong Kong Chinese news sources
RSS_FEEDS = {
    "yahoo_finance_hk": {
        "name": "Yahoo Finance HK",
        "feeds": [
            "https://hk.finance.yahoo.com/news/rssindex",
        ],
        "default_category": ["finance", "local"],
    },
    "hket": {
        "name": "香港經濟日報",
        "feeds": [
            "https://www.hket.com/rss/hongkong",
            "https://www.hket.com/rss/finance",
        ],
        "default_category": ["finance", "local"],
    },
}

# Web scraping sources (no RSS available)
SCRAPE_SOURCES = {
    "cnn_breaking": {
        "name": "CNN",
        "url": "https://edition.cnn.com/?refresh=1",
        "default_category": ["international"],
    },
    "hk01": {
        "name": "HK01",
        "url": "https://www.hk01.com",
        "default_category": ["local"],
    },
}


def load_existing_news():
    """Load existing news from JSON file"""
    if NEWS_FILE.exists():
        try:
            with open(NEWS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("articles", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def save_news(articles):
    """Save articles to JSON file"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "last_updated": datetime.now().isoformat(),
        "total": len(articles),
        "articles": articles
    }
    
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remove_old_articles(articles, max_age_days=MAX_AGE_DAYS):
    """Remove articles older than max_age_days"""
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    filtered = []
    
    for article in articles:
        pub_date_str = article.get("pubDate", "")
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str[:19], "%Y-%m-%d %H:%M:%S")
                if pub_date >= cutoff_date:
                    filtered.append(article)
            except ValueError:
                filtered.append(article)
        else:
            filtered.append(article)
    
    return filtered


def deduplicate_articles(articles):
    """Remove duplicates based on article_id and title"""
    seen_ids = set()
    seen_titles = set()
    unique = []
    
    for article in articles:
        article_id = article.get("id", "")
        title = article.get("title", "")
        
        if article_id and article_id in seen_ids:
            continue
        
        if title and title in seen_titles:
            continue
        
        if article_id:
            seen_ids.add(article_id)
        if title:
            seen_titles.add(title)
        
        unique.append(article)
    
    return unique


def sort_articles_by_date(articles):
    """Sort articles by publication date (newest first)"""
    def get_sort_key(article):
        pub_date_str = article.get("pubDate", "")
        ts = 0
        if pub_date_str:
            try:
                dt = datetime.strptime(pub_date_str[:19], "%Y-%m-%d %H:%M:%S")
                ts = dt.timestamp()
            except ValueError:
                pass
        # newsdata.io (non-rss) = 0, RSS = 1 → newsdata first within same time
        is_rss = 1 if "rss" in article.get("category", []) else 0
        return (-ts, is_rss)
    
    return sorted(articles, key=get_sort_key)


MAX_SOURCE_RATIO = 0.30  # 每個來源最多佔總數 30%


def cap_by_source(articles, max_ratio=MAX_SOURCE_RATIO):
    """每個來源最多佔總數 max_ratio，超出部分按日期排序移除最舊"""
    if not articles:
        return articles
    from collections import defaultdict
    by_src = defaultdict(list)
    for a in articles:
        by_src[a.get("source_name", "unknown")].append(a)
    total = len(articles)
    cap = max(1, int(total * max_ratio))
    trimmed = []
    for src, src_arts in by_src.items():
        trimmed.extend(src_arts[:cap])
    removed = total - len(trimmed)
    if removed > 0:
        print(f"[cap] 移除 {removed} 篇超額，每源上限 {cap} 篇")
    return trimmed


def interleave_sources(articles):
    """混合排列：同一來源嘅文章唔會相鄰（貪心算法）"""
    from collections import defaultdict, deque
    if not articles:
        return articles
    queues = defaultdict(deque)
    for a in articles:
        queues[a.get("source_name", "unknown")].append(a)
    result = []
    while queues:
        last_src = result[-1].get("source_name", "unknown") if result else None
        # 揀一個唔同於上一篇嘅來源
        picked = None
        for src in list(queues.keys()):
            if src != last_src:
                picked = queues[src].popleft()
                if not queues[src]:
                    del queues[src]
                break
        if picked is None:
            # 所有剩餘文章都同上一篇撞源，揀最多嘅嗰個
            src = max(queues, key=lambda s: len(queues[s]))
            picked = queues[src].popleft()
            if not queues[src]:
                del queues[src]
        result.append(picked)
    return result


def fetch_news(days=7, max_per_category=10):
    """
    Fetch Chinese news from NewsData.io using batched categories (2 API calls instead of 8)
    
    Args:
        days: Number of days to look back
        max_per_category: Maximum articles per category per region
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    articles = []
    
    print(f"Fetching Chinese news from NewsData.io...")
    print(f"Category batches: {len(CATEGORY_BATCHES)} (merged from 8 categories)")
    print(f"Regions: {', '.join(REGIONS)}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    for batch_idx, category_batch in enumerate(CATEGORY_BATCHES, 1):
        category_str = ','.join(category_batch)
        print(f"\nBatch {batch_idx}: {category_str}")
        batch_articles = []
        
        for region in REGIONS:
            print(f"  Region: {region}")
            page = None
            
            while len(batch_articles) < max_per_category * len(category_batch):
                params = {
                    "apikey": API_KEY,
                    "language": "zh",
                    "category": category_str,
                    "country": region,
                }
                
                if page:
                    params["page"] = page
                
                try:
                    response = requests.get(BASE_URL, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("status") != "success":
                        print(f"    API error: {data.get('message', 'Unknown error')}")
                        break
                    
                    results = data.get("results", [])
                    
                    if not results:
                        break
                    
                    for article in results:
                        pub_date_str = article.get("pubDate")
                        if pub_date_str:
                            try:
                                pub_date = datetime.strptime(pub_date_str[:19], "%Y-%m-%d %H:%M:%S")
                                if pub_date < start_date:
                                    continue
                            except ValueError:
                                pass
                        
                        processed = {
                            "id": article.get("article_id"),
                            "title": article.get("title"),
                            "description": article.get("description"),
                            "link": article.get("link"),
                            "pubDate": article.get("pubDate"),
                            "source_name": article.get("source_name"),
                            "image_url": "",
                            "keywords": article.get("keywords", []),
                            "category": article.get("category", category_batch[:1]),
                            "region": region,
                        }
                        
                        if not processed["title"]:
                            continue
                        
                        batch_articles.append(processed)
                        
                        if len(batch_articles) >= max_per_category * len(category_batch):
                            break
                    
                    next_page = data.get("next_page")
                    if not next_page or len(batch_articles) >= max_per_category * len(category_batch):
                        break
                    page = next_page
                    
                except requests.RequestException as e:
                    print(f"    Request error: {e}")
                    break
                except json.JSONDecodeError as e:
                    print(f"    JSON error: {e}")
                    break
        
        articles.extend(batch_articles)
        print(f"  Total for batch {batch_idx}: {len(batch_articles)} articles")
    
    return articles


def fetch_rss_feed(feed_url, source_name, source_key=None):
    """Fetch and parse RSS feed"""
    articles = []
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(feed_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        entries = feed.entries if hasattr(feed, 'entries') else []
        
        for entry in entries:
            title = entry.get('title', '')
            link = entry.get('link', '')
            
            if not title or not link:
                continue
            
            # 過濾娛樂新聞（所有來源）
            _ent_kw = ['演唱會', '藝人', '明星', '歌手', '演員', '頒獎', '紅館', '女主播', '影帝', '影后', '緋聞', '結婚', '離婚', '懷孕', '生仔', '女神', '偶像', '男團', '女團', '星二代', '八卦', 'TVB', '港姐', '離世', '悼念', '古天樂', '譚詠麟']
            if any(kw in title for kw in _ent_kw):
                continue
            
            # Generate ID
            content = f"{link}|{title}"
            article_id = hashlib.md5(content.encode()).hexdigest()[:16]
            
            # Parse date
            pub_date = None
            if hasattr(entry, 'published'):
                try:
                    pub_date = datetime.strptime(entry.published[:19], "%Y-%m-%dT%H:%M:%S")
                except:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_date = parsedate_to_datetime(entry.published)
                    except:
                        pass
            
            pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S") if pub_date else ""
            
            # Get description
            description = ""
            if hasattr(entry, 'description'):
                import re
                description = re.sub('<[^<]+?>', '', entry.description)
                description = description[:500]
            
            # 不抓取新聞來源圖片 — 顯示時用自家圖片庫（build_news_local.py theme_for()）
            image_url = ""
            
            article = {
                "id": article_id,
                "title": title,
                "description": description,
                "link": link,
                "pubDate": pub_date_str,
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": source_name,
                "image_url": image_url,
                "keywords": [],
                "category": RSS_FEEDS.get(source_key, {}).get("default_category", ["rss"]),
                "region": "hk",
            }
            
            articles.append(article)
        
        return articles
        
    except Exception as e:
        print(f"    Error: {e}")
        return []




HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

def scrape_cnn(url, source_name, category):
    """Scrape CNN breaking news from homepage — 只攞 article body 內容"""
    if not BeautifulSoup:
        print(f"    bs4 not available, skipping {source_name}")
        return []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        seen = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            title_text = a_tag.get_text(strip=True)
            if not title_text or len(title_text) < 15:
                continue
            # 只保留真正嘅新聞 article URL（/YYYY/MM/DD/ 格式）
            if "/video/" in href or "/gallery/" in href or "/live-news/" in href:
                continue
            if not re.search(r"/\d{4}/\d{2}/\d{2}/", href):
                continue
            if not href.startswith("http"):
                href = "https://edition.cnn.com" + href if href.startswith("/") else href
            article_id = hashlib.md5(href.encode()).hexdigest()
            if article_id in seen:
                continue
            seen.add(article_id)
            desc_tag = a_tag.find_next("p")
            desc = desc_tag.get_text(strip=True)[:500] if desc_tag else ""
            articles.append({
                "id": article_id,
                "title": title_text[:200],
                "description": desc,
                "link": href,
                "pubDate": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": source_name,
                "image_url": "",
                "keywords": [],
                "category": category,
                "region": "intl",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error {source_name}: {e}")
        return []

def scrape_hk01():
    """Scrape HK01 local news"""
    if not BeautifulSoup:
        print("    bs4 not available, skipping HK01")
        return []
    try:
        resp = requests.get("https://www.hk01.com/hk/1/即時新聞", headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            resp = requests.get("https://www.hk01.com", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        seen = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            title_text = a_tag.get_text(strip=True)
            if not title_text or len(title_text) < 8:
                continue
            if "/tag/" in href or "/topic/" in href or href.count("/") < 3:
                continue
            if not href.startswith("http"):
                href = "https://www.hk01.com" + href
            article_id = hashlib.md5(href.encode()).hexdigest()
            if article_id in seen:
                continue
            seen.add(article_id)
            articles.append({
                "id": article_id,
                "title": title_text[:200],
                "description": "",
                "link": href,
                "pubDate": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "HK01",
                "image_url": "",
                "keywords": [],
                "category": ["local"],
                "region": "hk",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error HK01: {e}")
        return []

def fetch_scraped_news():
    """Fetch news from web scraping sources"""
    all_articles = []
    print("\nScraping web sources...")
    print("  CNN Breaking...")
    arts = scrape_cnn("https://edition.cnn.com/?refresh=1", "CNN", ["international"])
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    print("  HK01...")
    arts = scrape_hk01()
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    return all_articles

# ===== 新聞價值評分（0-100）=====
# 財經/國際大事高分，一般地方/體育低分
_HIGH_VALUE_KW = [
    # 財經核心（80-100）
    "股", "市", "恒指", "恆指", "美股", "港股", "nasdaq", "dow", "利率", "利息", "加息", "減息",
    "債", "國債", "美債", "聯儲", "儲局", "通脹", "央行", "匯率", "美元", "港元",
    "金價", "黃金", "石油", "原油", "油價",
    "樓", "地產", "物業", "按揭", "租金", "發展商",
    "ipo", "上市", "停牌", "私有化", "回購", "派息", "股息",
    "基金", "etf", "投資", "理財", "證券",
    # 國際大事（70-90）
    "特朗普", "美國", "中國", "日本", "歐盟", "俄羅斯", "烏克蘭",
    "戰爭", "制裁", "關稅", "貿易戰", "地緣",
    "联合国", "聯合國", "北約", "nato",
    # 科技/產業（60-80）
    "晶片", "半導體", "nvidia", "輝達", "蘋果", "微軟", "谷歌", "ai", "人工智能",
    "電動車", "比亞迪", "tesla", "新能源",
    # 香港政策/經濟（60-80）
    "港府", "財政", "預算案", "金管局", "gdp", "經濟", "失業",
]
_LOW_VALUE_KW = [
    "體育", "足球", "籃球", "羽毛球", "乒乓",
    "健康", "飲食", "食譜", "減肥",
    "星座", "運程", "塔羅",
    "旅遊", "景點", "酒店",
    "天氣", "颱風", "暴雨",
]

def news_value_score(article):
    """評分 0-100，越高越值得報導"""
    title = str(article.get('title') or '').lower()
    desc = str(article.get('description') or '').lower()
    text = title + ' ' + desc
    cats = ' '.join(article.get('category', []) or []).lower()
    source = str(article.get('source_name') or '').lower()

    score = 40  # 基礎分
    # 高價值關鍵詞加分（每中一個 +15，上限 +60）
    bonus = 0
    for kw in _HIGH_VALUE_KW:
        if kw.lower() in text:
            bonus += 15
    score += min(bonus, 60)
    # 低價值關鍵詞扣分
    for kw in _LOW_VALUE_KW:
        if kw.lower() in text:
            score -= 20
    # 來源加分：財經來源更高分
    if 'finance' in source or '經濟' in source or 'yahoo' in source:
        score += 15
    if source == 'cnn':
        score += 10
    # 標題長度適中加分（20-80 字最理想）
    title_len = len(str(article.get('title') or ''))
    if 20 <= title_len <= 80:
        score += 5
    return max(0, min(100, score))


def filter_by_value(articles, min_score=35):
    """只保留高價值新聞"""
    scored = [(news_value_score(a), a) for a in articles]
    scored.sort(key=lambda x: x[0], reverse=True)
    filtered = [a for s, a in scored if s >= min_score]
    return filtered


def fetch_all_rss():
    """Fetch all RSS feeds and scrape extra sources"""
    all_articles = []
    
    print("\nFetching RSS feeds...")
    
    for source_key, source_info in RSS_FEEDS.items():
        print(f"  {source_info['name']}:")
        
        for feed_url in source_info['feeds']:
            articles = fetch_rss_feed(feed_url, source_info["name"], source_key)
            print(f"    Fetched {len(articles)} articles from {feed_url}")
            all_articles.extend(articles)
    
    # Add scraped web sources (CNN, HK01)
    scraped = fetch_scraped_news()
    all_articles.extend(scraped)
    
    return all_articles


def main(initial_build=False):
    """
    Main function
    
    Args:
        initial_build: If True, fetch more articles to build initial database
    """

    existing_articles = load_existing_news()
    print(f"Loaded {len(existing_articles)} existing articles")
    
    # Fetch from NewsData.io
    if initial_build:
        print("\n=== INITIAL BUILD MODE ===")
        print("Fetching from NewsData.io...")
        newsdata_articles = fetch_news(days=7, max_per_category=MAX_PER_CATEGORY_INITIAL)
    else:
        print("\nFetching from NewsData.io...")
        newsdata_articles = fetch_news(days=1, max_per_category=MAX_PER_CATEGORY_NORMAL)
    
    # Fetch from RSS feeds
    rss_articles = fetch_all_rss()
    
    # Merge all sources
    new_articles = newsdata_articles + rss_articles
    
    if not new_articles:
        print("No new articles fetched!")
        return
    
    print(f"\nFetched {len(new_articles)} new articles (NewsData: {len(newsdata_articles)}, RSS: {len(rss_articles)})")
    
    all_articles = existing_articles + new_articles
    print(f"Total before dedup: {len(all_articles)}")
    
    all_articles = deduplicate_articles(all_articles)
    duplicates_removed = len(existing_articles) + len(new_articles) - len(all_articles)
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicates")
    
    before_age_filter = len(all_articles)
    all_articles = remove_old_articles(all_articles)
    old_removed = before_age_filter - len(all_articles)
    if old_removed > 0:
        print(f"Removed {old_removed} articles older than {MAX_AGE_DAYS} days")
    
    all_articles = sort_articles_by_date(all_articles)
    
    # 新聞價值過濾：只保留高價值新聞
    before_value = len(all_articles)
    all_articles = filter_by_value(all_articles, min_score=35)
    low_value_removed = before_value - len(all_articles)
    if low_value_removed > 0:
        print(f"Removed {low_value_removed} low-value articles")
    
    # 每個來源最多 30%
    all_articles = cap_by_source(all_articles)
    
    # 混合排列：同一來源唔相鄰
    all_articles = interleave_sources(all_articles)
    
    save_news(all_articles)
    print(f"\n✅ Total: {len(all_articles)} articles saved")
    


if __name__ == "__main__":
    import sys
    
    initial = "--initial" in sys.argv
    
    if initial:
        print("=" * 50)
        print("INITIAL BUILD MODE")
        print("Building news database with max quota")
        print("=" * 50)
    
    main(initial_build=initial)
