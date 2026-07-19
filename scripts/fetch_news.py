#!/usr/bin/env python3
"""
Fetch Chinese news from NewsData.io for sicsicduck.com
Incremental mode: keeps old news, deduplicates, removes articles older than 30 days
Expanded regions: HK + Taiwan + China
Expanded categories: added 'world'
"""

import requests
import json
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

# Categories and regions (removed 'cn' to exclude Simplified Chinese news)
CATEGORIES = ['business', 'technology', 'entertainment', 'sports', 'science', 'health', 'politics', 'world']
REGIONS = ['hk', 'tw']


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
        if pub_date_str:
            try:
                return datetime.strptime(pub_date_str[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return datetime.min
    
    return sorted(articles, key=get_sort_key, reverse=True)


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
    
    if initial_build:
        print("\n=== INITIAL BUILD MODE ===")
        print("Fetching maximum articles to build initial database...")
        new_articles = fetch_news(days=7, max_per_category=MAX_PER_CATEGORY_INITIAL)
    else:
        new_articles = fetch_news(days=1, max_per_category=MAX_PER_CATEGORY_NORMAL)
    
    if not new_articles:
        print("No new articles fetched!")
        return
    
    print(f"\nFetched {len(new_articles)} new articles")
    
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