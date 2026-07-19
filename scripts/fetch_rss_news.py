#!/usr/bin/env python3
"""
Fetch Hong Kong news from RSS feeds
Supports: RTHK, SCMP, Hong Kong Economic Times, Ming Pao
"""

import feedparser
import json
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import requests
from urllib.parse import urlparse

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
NEWS_FILE = DATA_DIR / "news.json"

# RSS Feeds - Hong Kong news sources
RSS_FEEDS = {
    "rthk": {
        "name": "香港電台",
        "feeds": [
            "https://news.rthk.hk/rthk/en/latestnews.json",  # RTHK JSON feed
            "https://news.rthk.hk/rthk/en/component/k2最新聞.rss",  # Latest news
        ]
    },
    "scmp": {
        "name": "South China Morning Post",
        "feeds": [
            "https://www.scmp.com/rss/91/feed",  # Hong Kong news
            "https://www.scmp.com/rss/2/feed",   # Business
        ]
    },
    "hket": {
        "name": "香港經濟日報",
        "feeds": [
            "https://www.hket.com/rss/hongkong",
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


def generate_article_id(url, title):
    """Generate unique ID from URL and title"""
    content = f"{url}|{title}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def parse_date(date_str):
    """Parse various date formats"""
    if not date_str:
        return None
    
    # Try different formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None


def fetch_rss_feed(feed_url, source_name):
    """Fetch and parse RSS feed"""
    articles = []
    
    try:
        print(f"  Fetching {feed_url}...")
        
        # Use requests to get content first (better encoding handling)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(feed_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse with feedparser
        feed = feedparser.parse(response.content)
        
        if feed.bozo and feed.bozo_exception:
            print(f"    Warning: {feed.bozo_exception}")
        
        entries = feed.entries if hasattr(feed, 'entries') else []
        print(f"    Found {len(entries)} entries")
        
        for entry in entries:
            title = entry.get('title', '')
            link = entry.get('link', '')
            
            if not title or not link:
                continue
            
            # Generate ID
            article_id = generate_article_id(link, title)
            
            # Parse date
            pub_date = None
            if hasattr(entry, 'published'):
                pub_date = parse_date(entry.published)
            elif hasattr(entry, 'pubDate'):
                pub_date = parse_date(entry.pubDate)
            elif hasattr(entry, 'updated'):
                pub_date = parse_date(entry.updated)
            
            # Format date
            pub_date_str = ""
            if pub_date:
                pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get description
            description = ""
            if hasattr(entry, 'description'):
                description = entry.description
            elif hasattr(entry, 'summary'):
                description = entry.summary
            
            # Clean HTML from description
            import re
            description = re.sub('<[^<]+?>', '', description)
            description = description[:500] if description else ""
            
            article = {
                "id": article_id,
                "title": title,
                "description": description,
                "link": link,
                "pubDate": pub_date_str,
                "source_name": source_name,
                "image_url": "",
                "keywords": [],
                "category": ["rss", "local"],
                "region": "hk",
            }
            
            articles.append(article)
        
        return articles
        
    except Exception as e:
        print(f"    Error: {e}")
        return []


def fetch_all_rss():
    """Fetch all RSS feeds"""
    all_articles = []
    
    print("Fetching RSS feeds from Hong Kong media...")
    
    for source_key, source_info in RSS_FEEDS.items():
        print(f"\n{source_info['name']}:")
        
        for feed_url in source_info['feeds']:
            articles = fetch_rss_feed(feed_url, source_info['name'])
            all_articles.extend(articles)
    
    return all_articles


def deduplicate_articles(articles):
    """Remove duplicates based on ID and title"""
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


def remove_old_articles(articles, max_age_days=30):
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


def main():
    """Main function"""
    # Load existing news
    existing_articles = load_existing_news()
    print(f"Loaded {len(existing_articles)} existing articles")
    
    # Fetch RSS news
    rss_articles = fetch_all_rss()
    print(f"\nFetched {len(rss_articles)} RSS articles")
    
    # Merge old and new
    all_articles = existing_articles + rss_articles
    print(f"Total before dedup: {len(all_articles)}")
    
    # Deduplicate
    all_articles = deduplicate_articles(all_articles)
    duplicates_removed = len(existing_articles) + len(rss_articles) - len(all_articles)
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicates")
    
    # Remove old articles
    before_age_filter = len(all_articles)
    all_articles = remove_old_articles(all_articles)
    old_removed = before_age_filter - len(all_articles)
    if old_removed > 0:
        print(f"Removed {old_removed} articles older than 30 days")
    
    # Sort by date
    all_articles = sort_articles_by_date(all_articles)
    
    # Save
    save_news(all_articles)
    print(f"\n✅ Total: {len(all_articles)} articles saved")


if __name__ == "__main__":
    main()
