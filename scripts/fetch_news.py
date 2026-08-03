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
from datetime import datetime, timedelta
from pathlib import Path

# API Configuration
API_KEY = "pub_00e12f838504473cab89480d31d35522"
BASE_URL = "https://newsdata.io/api/1/news"

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
NEWS_FILE = DATA_DIR / "news.json"

# Settings
MAX_AGE_DAYS = 30  # Remove articles older than this
MAX_PER_CATEGORY_NORMAL = 10  # Max articles per category per region for daily cron
MAX_PER_CATEGORY_INITIAL = 50  # Max articles per category per region for initial build

# Categories and regions (removed 'cn' and 'tw' to exclude Simplified Chinese and Taiwan news)
CATEGORIES = ['business', 'technology', 'entertainment', 'sports', 'science', 'health', 'politics', 'world']
REGIONS = ['hk']

# RSS Feeds - Hong Kong Chinese news sources
RSS_FEEDS = {
    "hket": {
        "name": "香港經濟日報",
        "feeds": [
            "https://www.hket.com/rss/hongkong",
            "https://www.hket.com/rss/finance",
        ]
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
    Fetch Chinese news from NewsData.io from multiple categories and regions
    
    Args:
        days: Number of days to look back
        max_per_category: Maximum articles per category per region
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    articles = []
    
    print(f"Fetching Chinese news from NewsData.io...")
    print(f"Categories: {', '.join(CATEGORIES)}")
    print(f"Regions: {', '.join(REGIONS)}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    for category in CATEGORIES:
        print(f"\nFetching {category} news...")
        category_articles = []
        
        for region in REGIONS:
            print(f"  Region: {region}")
            page = None
            
            while len(category_articles) < max_per_category:
                params = {
                    "apikey": API_KEY,
                    "language": "zh",
                    "category": category,
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
                            "category": article.get("category", [category]),
                            "region": region,
                        }
                        
                        if not processed["title"]:
                            continue
                        
                        category_articles.append(processed)
                        
                        if len(category_articles) >= max_per_category:
                            break
                    
                    next_page = data.get("next_page")
                    if not next_page or len(category_articles) >= max_per_category:
                        break
                    page = next_page
                    
                except requests.RequestException as e:
                    print(f"    Request error: {e}")
                    break
                except json.JSONDecodeError as e:
                    print(f"    JSON error: {e}")
                    break
        
        articles.extend(category_articles)
        print(f"  Total for {category}: {len(category_articles)} articles")
    
    return articles


def fetch_rss_feed(feed_url, source_name):
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
                "source_name": source_name,
                "image_url": image_url,
                "keywords": [],
                "category": ["rss"],
                "region": "hk",
            }
            
            articles.append(article)
        
        return articles
        
    except Exception as e:
        print(f"    Error: {e}")
        return []


def fetch_hkej_instantnews():
    """Scrape 信報即時新聞 page (no RSS available, paywalled site)"""
    articles = []
    url = "https://www.hkej.com/instantnews"
    
    print("\nScraping 信報即時新聞...")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        import re
        html = response.text
        
        # 搵 article links: /instantnews/xxx/article/数字/标题
        # 每條新聞嘅格式:
        # /instantnews/section/article/id/...
        # 後面跟住 #### [title](link)
        # 同埋 description（如果有）
        
        # Match pattern: 路徑 + 標題 + 可能嘅描述
        article_pattern = re.compile(
            r'/instantnews/([^/]+)/article/(\d+)/([^"\s]+)'
        )
        
        seen_urls = set()
        
        for match in article_pattern.finditer(html):
            section = match.group(1)
            article_id = match.group(2)
            slug = match.group(3)
            link = f"https://www.hkej.com/instantnews/{section}/article/{article_id}/{slug}"
            
            if link in seen_urls:
                continue
            seen_urls.add(link)
            
            # 喺 link 附近搵 title
            # 常見 pattern: #### [title](/instantnews/...)
            # 或者 <a href="...">title</a>
            link_start = html.find(f'/instantnews/{section}/article/{article_id}/{slug}')
            if link_start < 0:
                continue
            
            # 向前搵 title
            before = html[max(0, link_start - 300):link_start]
            
            # 嘗試 match: #### [title](link)
            title_match = re.search(r'####\s*\[([^\]]+)\]\([^)]+\)', before)
            if not title_match:
                # 嘗試 match: <a href="...">title</a>
                title_match = re.search(r'<a[^>]*href="[^"]*' + re.escape(f'/instantnews/{section}/article/{article_id}') + r'[^"]*"[^>]*>([^<]+)</a>', html[:link_start + 500])
            
            if not title_match:
                continue
            
            title = title_match.group(1).strip()
            if not title:
                continue
            
            # 喺 title 附近搵 description（如果有）
            desc = ""
            after_link = html[link_start:link_start + 500]
            desc_match = re.search(r'</a>\s*</h\d>\s*<p[^>]*>([^<]+)', after_link)
            if desc_match:
                desc = desc_match.group(1).strip()[:300]
            
            # Map section to category
            section_map = {
                "stock": "business",
                "market": "business",
                "finance": "business",
                "property": "business",
                "china": "business",
                "international": "world",
                "current": "politics",
                "announcement": "business",
                "comment": "business",
            }
            category = section_map.get(section, "business")
            
            # Generate ID from URL
            content = f"hkej-{link}"
            uid = hashlib.md5(content.encode()).hexdigest()[:16]
            
            article = {
                "id": uid,
                "title": title,
                "description": desc,
                "link": link,
                "pubDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_name": "信報",
                "image_url": "",
                "keywords": [],
                "category": [category],
                "region": "hk",
            }
            
            articles.append(article)
            
            if len(articles) >= 50:
                break
        
        print(f"  Fetched {len(articles)} articles from 信報即時新聞")
        
    except Exception as e:
        print(f"  Error scraping 信報: {e}")
    
    return articles


def fetch_all_rss():
    """Fetch all RSS feeds and scrape extra sources"""
    all_articles = []
    
    print("\nFetching RSS feeds...")
    
    for source_key, source_info in RSS_FEEDS.items():
        print(f"  {source_info['name']}:")
        
        for feed_url in source_info['feeds']:
            articles = fetch_rss_feed(feed_url, source_info['name'])
            print(f"    Fetched {len(articles)} articles from {feed_url}")
            all_articles.extend(articles)
    
    # 額外 source: 信報即時新聞 (scrape)
    hkej_articles = fetch_hkej_instantnews()
    all_articles.extend(hkej_articles)
    
    return all_articles


def generate_html_content(articles):
    """Generate HTML content for news cards"""
    html = ""
    
    for article in articles:
        image_url = article.get("image_url") or ""
        link = article.get("link", "#")
        description = article.get("description", "")
        category_list = article.get("category", [])
        category_str = ", ".join(category_list) if category_list else ""
        region = article.get("region", "")
        
        if image_url:
            image_html = f'<img src="{image_url}" alt="" onerror="this.src=\'/default-news.jpg\'">'
        else:
            image_html = '<img src="/default-news.jpg" alt="">'
        
        html += f'''        <a href="{link}" target="_blank" class="article-card" data-category="{category_str}" data-region="{region}">
            <div class="article-image">{image_html}</div>
            <div class="article-content">
                <h3 class="article-title">{article["title"]}</h3>
                <p class="article-description">{description}</p>
                <div class="article-meta">
                    <span class="article-source">{article.get("source_name", "")}</span>
                    <span class="article-date">📅 {article.get("pubDate", "")[:10] if article.get("pubDate") else ""}</span>
                </div>
            </div>
        </a>
'''
    
    return html


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
    
    html_content = generate_html_content(all_articles)
    
    news_html_path = SCRIPT_DIR.parent / "news.html"
    with open(news_html_path, "r", encoding="utf-8") as f:
        html_content_full = f.read()
    
    import re
    pattern = r'<div class="articles-grid" id="articlesGrid">.*?</section>'
    replacement = f'<div class="articles-grid" id="articlesGrid">\n{html_content}    </div>\n</section>'
    
    new_html = re.sub(pattern, replacement, html_content_full, flags=re.DOTALL)
    
    with open(news_html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"Updated {news_html_path}")


if __name__ == "__main__":
    import sys
    
    initial = "--initial" in sys.argv
    
    if initial:
        print("=" * 50)
        print("INITIAL BUILD MODE")
        print("Building news database with max quota")
        print("=" * 50)
    
    main(initial_build=initial)