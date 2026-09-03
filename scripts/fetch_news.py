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
    ['entertainment', 'sports', 'politics', 'world'],
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
    "cnn_world": {
        "name": "CNN",
        "url": "https://edition.cnn.com/world",
        "default_category": ["international"],
    },
    "cnn_business": {
        "name": "CNN Business",
        "url": "https://edition.cnn.com/business",
        "default_category": ["finance", "us"],
    },
    "hk01": {
        "name": "HK01",
        "url": "https://www.hk01.com",
        "default_category": ["local"],
    },
    "investing": {
        "name": "Investing.com",
        "url": "https://www.investing.com/news/financial-news",
        "default_category": ["finance", "us"],
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
                            "image_url": article.get("image_url"),
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
            
            # Extract image from RSS enclosures / media_content
            image_url = ""
            # 1) enclosure entries (standard RSS) that are images
            for enc in entry.get('enclosures', []):
                enc_type = enc.get('type', '')
                enc_href = enc.get('href') or enc.get('url', '')
                if enc_href and (enc_type.startswith('image') or enc_href.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))):
                    # Skip generic SEO placeholder images (site logo/default artwork)
                    if '/image/seo/' in enc_href or 'logo' in enc_href.lower():
                        continue
                    image_url = enc_href
                    break
            # 2) media_content (Media RSS)
            if not image_url:
                for mc in entry.get('media_content', []):
                    mc_url = mc.get('url') or mc.get('href', '')
                    if mc_url and mc_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        image_url = mc_url
                        break
            # 3) thumbnail (Media RSS)
            if not image_url and entry.get('media_thumbnail'):
                th = entry['media_thumbnail']
                if isinstance(th, list) and th:
                    image_url = th[0].get('url', '') if isinstance(th[0], dict) else ''
                elif isinstance(th, dict):
                    image_url = th.get('url', '')
            
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
    """Scrape CNN news pages"""
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
            if not title_text or len(title_text) < 10:
                continue
            if "/video/" in href or "/gallery/" in href or "/live-news/" in href:
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

def scrape_investing():
    """Fetch Investing.com financial news via RSS (HTML page returns 403)"""
    if not BeautifulSoup:
        print("    bs4 not available, skipping Investing.com")
        return []
    try:
        resp = requests.get("https://www.investing.com/rss/news_25.rss", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        articles = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            desc = item.findtext("description", "")
            pub = item.findtext("pubDate", "")
            if not title or not link:
                continue
            article_id = hashlib.md5(link.encode()).hexdigest()
            # Parse pubDate if available
            pub_str = ""
            if pub:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub)
                    pub_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            else:
                pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            articles.append({
                "id": article_id,
                "title": title[:200],
                "description": desc[:500] if desc else "",
                "link": link,
                "pubDate": pub_str,
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "Investing.com",
                "image_url": "",
                "keywords": [],
                "category": ["finance", "us"],
                "region": "us",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error Investing.com: {e}")
        return []

def fetch_scraped_news():
    """Fetch news from web scraping sources"""
    all_articles = []
    print("\nScraping web sources...")
    print("  CNN World...")
    arts = scrape_cnn("https://edition.cnn.com/world", "CNN", ["international"])
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    print("  CNN Business...")
    arts = scrape_cnn("https://edition.cnn.com/business", "CNN Business", ["finance", "us"])
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    print("  HK01...")
    arts = scrape_hk01()
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    print("  Investing.com...")
    arts = scrape_investing()
    print(f"    Fetched {len(arts)} articles")
    all_articles.extend(arts)
    return all_articles




            # Parse pubDate if available
            pub_str = ""
            if pub:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub)
                    pub_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            else:
                pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            articles.append({
                "id": article_id,
                "title": title[:200],
                "description": desc[:500] if desc else "",
                "link": link,
                "pubDate": pub_str,
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "Investing.com",
                "image_url": "",
                "keywords": [],
                "category": ["finance", "us"],
                "region": "us",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error Investing.com: {e}")
        return []

            # Parse pubDate if available
            pub_str = ""
            if pub:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub)
                    pub_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            else:
                pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            articles.append({
                "id": article_id,
                "title": title[:200],
                "description": desc[:500] if desc else "",
                "link": link,
                "pubDate": pub_str,
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "Investing.com",
                "image_url": "",
                "keywords": [],
                "category": ["finance", "us"],
                "region": "us",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error Investing.com: {e}")
        return []

            # Parse pubDate if available
            pub_str = ""
            if pub:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub)
                    pub_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            else:
                pub_str = datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
            articles.append({
                "id": article_id,
                "title": title[:200],
                "description": desc[:500] if desc else "",
                "link": link,
                "pubDate": pub_str,
                "fetched_at": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "Investing.com",
                "image_url": "",
                "keywords": [],
                "category": ["finance", "us"],
                "region": "us",
            })
        return articles[:15]
    except Exception as e:
        print(f"    Scrape error Investing.com: {e}")
        return []

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
    
    # Add scraped web sources (CNN, HK01, Investing.com)
    scraped = fetch_scraped_news()
    all_articles.extend(scraped)
    
    return all_articles


def load_summary(aid):
    """讀取已改寫嘅摘要; 無就回 None"""
    if not aid:
        return None
    p = CACHE_DIR / f"{aid}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("status") == "done" and d.get("rewritten"):
            return d["rewritten"]
    except (json.JSONDecodeError, OSError):
        pass
    return None


def generate_html_content(articles):
    """Generate HTML content for news cards"""
    html = ""
    modals = []

    for article in articles:
        aid = article.get("id", "")
        image_url = article.get("image_url") or ""
        link = article.get("link", "#")
        description = article.get("description", "")
        category_list = article.get("category", [])
        category_str = ", ".join(category_list) if category_list else ""
        region = article.get("region", "")
        title = article.get("title", "")
        source = article.get("source_name", "")
        pub = (article.get("pubDate", "") or "")[:10]

        if image_url:
            image_html = f'<img src="{image_url}" alt="" onerror="this.src=\'/default-news.jpg\'">'
        else:
            image_html = '<img src="/default-news.jpg" alt="">'

        # 有站內摘要 → 用 modal 卡片
        summary = load_summary(aid)
        if summary:
            summary_esc = html_lib.escape(summary, quote=True)
            title_esc = html_lib.escape(title, quote=True)
            aid_esc = html_lib.escape(aid, quote=True)
            src_esc = html_lib.escape(source, quote=True)
            pub_esc = html_lib.escape(pub, quote=True)
            link_esc = html_lib.escape(link, quote=True)

            html += f'''        <a href="javascript:void(0)" class="article-card" data-modal-id="{aid_esc}" data-category="{html_lib.escape(category_str, quote=True)}" data-region="{html_lib.escape(region, quote=True)}">
            <div class="article-image">{image_html}</div>
            <div class="article-content">
                <h3 class="article-title">{title_esc}</h3>
                <p class="article-description">{summary_esc}</p>
                <div class="article-meta">
                    <span class="article-source">{src_esc}</span>
                    <span class="article-date">📅 {pub_esc}</span>
                </div>
            </div>
        </a>
'''
            modals.append(f'''<div class="news-modal" id="modal-{aid_esc}" data-modal>
        <div class="news-modal-backdrop" onclick="closeModal('{aid_esc}')"></div>
        <div class="news-modal-dialog">
            <button class="news-modal-close" onclick="closeModal('{aid_esc}')">✕</button>
            <h2 class="news-modal-title">{title_esc}</h2>
            <div class="news-modal-meta">
                <span class="article-source">{src_esc}</span>
                <span class="article-date">📅 {pub_esc}</span>
            </div>
            <div class="news-modal-body">
                <p class="news-modal-rewritten">{summary_esc}</p>
                <p class="news-modal-copy">* 以上內容為本站以人工智能改寫之摘要，版權屬原媒體所有。</p>
            </div>
            <div class="news-modal-footer">
                <a class="news-modal-link" href="{link_esc}" target="_blank" rel="noopener">📄 閱讀原文 →</a>
            </div>
        </div>
    </div>''')
        else:
            html += f'''        <a href="{link}" target="_blank" class="article-card" data-category="{category_str}" data-region="{region}">
            <div class="article-image">{image_html}</div>
            <div class="article-content">
                <h3 class="article-title">{title}</h3>
                <p class="article-description">{description}</p>
                <div class="article-meta">
                    <span class="article-source">{source}</span>
                    <span class="article-date">📅 {pub}</span>
                </div>
            </div>
        </a>
'''

    return html, modals


def main(initial_build=False, build_only=False):
    """
    Main function
    
    Args:
        initial_build: If True, fetch more articles to build initial database
        build_only: If True, skip fetching, just rebuild news.html from news.json
    """
    if build_only:
        # 由已存 news.json 重新 build news.html（唔重新抓取）
        articles = load_existing_news()
        html_content, modals = generate_html_content(articles)
        _rebuild_html(html_content, modals, mode="build-only")
        return

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
    
    # Backfill: fill missing image_url in existing articles from newly fetched ones
    # (RSS sources previously stored empty images; enrich them on next runs)
    existing_by_id = {a.get('id'): a for a in existing_articles if a.get('id')}
    backfilled = 0
    for na in new_articles:
        if not na.get('image_url'):
            continue
        nid = na.get('id')
        if nid and nid in existing_by_id:
            old = existing_by_id[nid]
            if not old.get('image_url') and old.get('image_url') != na['image_url']:
                old['image_url'] = na['image_url']
                backfilled += 1
    if backfilled:
        print(f"Backfilled {backfilled} existing articles with missing images")
    
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
    
    # Ensure newsdata.io articles appear above RSS articles
    non_rss = [a for a in all_articles if "rss" not in a.get("category", [])]
    rss = [a for a in all_articles if "rss" in a.get("category", [])]
    all_articles = non_rss + rss
    
    save_news(all_articles)
    print(f"\n✅ Total: {len(all_articles)} articles saved")
    
    html_content, modals = generate_html_content(all_articles)

    html_content, modals = generate_html_content(all_articles)
    _rebuild_html(html_content, modals)


def _rebuild_html(html_content, modals, mode=""):
    """重建 news.html：替換 articles-grid + 剷走舊 modal + 注入新 modal + CSS/JS"""
    import re
    news_html_path = SCRIPT_DIR.parent / "news.html"
    html_content_full = news_html_path.read_text(encoding="utf-8")

    # 1) 剷走所有舊 modal block（避免每次 build 累積重複），保留 articles-grid
    #    舊 modal 喺 grid section (</section>) 之後緊接
    grid_pattern = r'<div class="articles-grid" id="articlesGrid">.*?</section>'
    m = re.search(grid_pattern, html_content_full, flags=re.DOTALL)
    if not m:
        print("❌ 唔該到 articlesGrid，中止")
        return
    section_end = m.end()

    # 由 section 結尾起，剷走緊接嘅連續 modal block
    rest = html_content_full[section_end:]
    while True:
        mm = re.match(r'\s*(<div class="news-modal"[\s\S]*?</div>\s*</div>\s*</div>)', rest)
        if not mm:
            break
        block = mm.group(1)
        # 確認係完整 modal（有 backdrop + dialog）
        if '<div class="news-modal-backdrop"' not in block or \
           '<div class="news-modal-dialog"' not in block:
            break
        rest = rest[mm.end():]

    # 2) 重組：grid 內容 + 新 modal + 剷除後嘅其餘內容
    modals_html = "\n".join(modals) if modals else ""
    cleaned = (html_content_full[:m.start()] +
               f'<div class="articles-grid" id="articlesGrid">\n{html_content}    </div>\n</section>'
               + (f'\n\n{modals_html}' if modals_html else '')
               + rest)

    # 3) 注入 modal CSS + JS（強制更新 CSS，避免舊版 position:relative 殘留）
    new_css = _MODAL_CSS()
    if "/* ==== 站內新聞 Modal CSS ==== */" in cleaned:
        # 已存在 → 替換成新版 CSS
        cleaned = re.sub(
            r'<style>\s*/\* ==== 站內新聞 Modal CSS ==== \*/.*?</style>',
            new_css, cleaned, count=1, flags=re.DOTALL)
    else:
        # 唔存在 → 插去第一個 </style> 前面
        cleaned = re.sub(r'(</style>)', new_css + r'\1', cleaned, count=1, flags=re.DOTALL)
    if "function openModal" not in cleaned:
        cleaned = re.sub(r'(</body>)', _MODAL_JS() + r'\1', cleaned, count=1, flags=re.DOTALL)

    news_html_path.write_text(cleaned, encoding="utf-8")
    label = f"[{mode}] " if mode else ""
    print(f"{label}Updated {news_html_path.name} (modal: {len(modals)})")


def _MODAL_CSS():
    return r"""<style>
/* ==== 站內新聞 Modal CSS ==== */
.news-modal { display: none; position: fixed; inset: 0; z-index: 300; }
.news-modal.open { display: block; }
.news-modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.55); backdrop-filter: blur(2px); }
.news-modal-dialog { position: fixed; z-index: 302; max-width: 640px; width: calc(100% - 32px); top: 6vh; left: 50%; transform: translateX(-50%); background: #fff; border-radius: 16px; box-shadow: 0 24px 48px rgba(0,0,0,.3); padding: 28px 28px 24px; max-height: 82vh; overflow-y: auto; border: 1px solid #e6c97c; }
.news-modal-close { position: absolute; top: 14px; right: 14px; width: 32px; height: 32px; border: none; border-radius: 50%; background: #f3f4f6; color: #6b7280; font-size: 16px; cursor: pointer; }
.news-modal-close:hover { background: #fdeed2; color: #7c5d1e; }
.news-modal-title { font-size: 20px; font-weight: 800; color: #111827; margin: 4px 40px 10px 0; line-height: 1.4; }
.news-modal-meta { display: flex; gap: 14px; align-items: center; font-size: 13px; color: #a16e12; margin-bottom: 16px; }
.news-modal-body { border-top: 1px solid #e5e7eb; padding-top: 16px; }
.news-modal-rewritten { font-size: 16px; line-height: 1.75; color: #1f2937; }
.news-modal-copy { margin-top: 16px; font-size: 12px; color: #6b7280; background: #fdf6e3; border-left: 3px solid #d9a928; padding: 8px 12px; border-radius: 6px; }
.news-modal-footer { margin-top: 20px; text-align: right; }
.news-modal-link { display: inline-block; padding: 10px 20px; background: linear-gradient(135deg, #d9a928, #b8860b); color: #fff; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 14px; }
.news-modal-link:hover { filter: brightness(1.05); }
</style>"""


def _MODAL_JS():
    return r"""<script>
// Modal 開關
function openModal(id) {
    const m = document.getElementById('modal-' + id);
    if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; }
}
function closeModal(id) {
    const m = document.getElementById('modal-' + id);
    if (m) { m.classList.remove('open'); document.body.style.overflow = ''; }
}
document.querySelectorAll('.article-card[data-modal-id]').forEach(card => {
    card.addEventListener('click', (e) => {
        e.preventDefault();
        openModal(card.dataset.modalId);
    });
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.news-modal.open').forEach(m => closeModal(m.id.replace('modal-','')));
    }
});
</script>"""


if __name__ == "__main__":
    import sys
    
    initial = "--initial" in sys.argv
    
    if initial:
        print("=" * 50)
        print("INITIAL BUILD MODE")
        print("Building news database with max quota")
        print("=" * 50)
    
    main(initial_build=initial)
