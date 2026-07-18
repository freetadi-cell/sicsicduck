#!/usr/bin/env python3
"""
Fetch Chinese news from NewsData.io for sicsicduck.com
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

def fetch_news(days=7, max_per_category=10):
    """
    Fetch Chinese news from NewsData.io from multiple categories
    
    Args:
        days: Number of days to look back
        max_per_category: Maximum articles per category
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    articles = []
    
    # Categories to fetch
    categories = ['business', 'technology', 'entertainment', 'sports', 'science', 'health', 'politics']
    
    print(f"Fetching Chinese news from NewsData.io...")
    print(f"Categories: {', '.join(categories)}")
    
    for category in categories:
        print(f"\nFetching {category} news...")
        category_articles = []
        page = None
        
        while len(category_articles) < max_per_category:
            params = {
                "apikey": API_KEY,
                "language": "zh",
                "category": category,
                "country": "hk",
            }
            
            if page:
                params["page"] = page
            
            try:
                response = requests.get(BASE_URL, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "success":
                    print(f"  API error: {data.get('message', 'Unknown error')}")
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
                print(f"  Request error: {e}")
                break
            except json.JSONDecodeError as e:
                print(f"  JSON error: {e}")
                break
        
        articles.extend(category_articles)
        print(f"  Fetched {len(category_articles)} articles from {category}")
    
    return articles

def save_news(articles):
    """Save articles to JSON file with deduplication and source filtering"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Remove duplicates based on title
    seen_titles = set()
    unique_articles = []
    for article in articles:
        title = article.get('title', '')
        link = article.get('link', '')
        
        # Filter out HK01 and Singtao news sources
        if 'hk01.com' in link or 'singtao' in link.lower() or 'stheadline' in link.lower():
            print(f"Filtered out: {article.get('source_name', '')} - {title[:30]}")
            continue
        
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)
    
    data = {
        "last_updated": datetime.now().isoformat(),
        "total": len(unique_articles),
        "articles": unique_articles
    }
    
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    removed = len(articles) - len(unique_articles)
    if removed > 0:
        print(f"Removed {removed} articles (duplicates + filtered sources)")
    print(f"\nTotal: {len(unique_articles)} articles saved to {NEWS_FILE}")

def generate_html_content(articles):
    """Generate HTML content for news cards"""
    html = ""
    
    for article in articles:
        image_url = article.get("image_url") or ""
        link = article.get("link", "#")
        description = article.get("description", "")
        category_list = article.get("category", [])
        category_str = ", ".join(category_list) if category_list else ""
        
        # Fix HK01 deep links - force browser open
        if "hk01.com" in link:
            # Add parameter to force web version
            if "?" in link:
                link = link + "&ref=browser"
            else:
                link = link + "?ref=browser"
        
        # Image HTML: use <img> tag with onerror fallback to default image
        if image_url:
            image_html = f'<img src="{image_url}" alt="" onerror="this.src=\'/default-news.jpg\'">'
        else:
            image_html = '<img src="/default-news.jpg" alt="">'
        
        html += f'''        <a href="{link}" target="_blank" class="article-card" data-category="{category_str}">
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

def main():
    articles = fetch_news(days=7, max_per_category=10)
    
    if not articles:
        print("No articles fetched!")
        return
    
    save_news(articles)
    
    html_content = generate_html_content(articles)
    
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
    main()