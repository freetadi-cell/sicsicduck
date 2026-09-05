#!/bin/bash
set -e

cd "$(dirname "$0")/.."
DIR=$(pwd)
OUT="$DIR/news.html"
DATA="$DIR/data"

mkdir -p "$DATA"

# --- 1. Fetch RSS feeds ---
echo "Fetching RSS feeds..."

python3 - << 'PYEOF'
import feedparser
import json
import os
import sys
from datetime import datetime, timezone

DATA_DIR = os.environ.get("DATA_DIR", "/home/freet/.openclaw/workspace/sicsicduck/data")

feeds = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "reuters_markets": "https://feeds.reuters.com/reuters/marketsNews",
    "yahoo_finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
    "cnbc_top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories",
    "bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
}

all_stories = []

for name, url in feeds.items():
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries[:8]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            if not title:
                continue
            all_stories.append({
                "source": name.replace("_", " ").title(),
                "title": title,
                "link": link,
                "summary": summary[:500] if summary else "",
                "published": entry.get("published", ""),
            })
            count += 1
        print(f"  {name}: {count} stories", file=sys.stderr)
    except Exception as e:
        print(f"  {name}: FAILED ({e})", file=sys.stderr)

out_path = os.path.join(DATA_DIR, "raw_stories.json")
with open(out_path, "w") as f:
    json.dump(all_stories, f, indent=2, ensure_ascii=False)

print(f"Fetched {len(all_stories)} total stories")
PYEOF

# --- 2. Summarize and rank with AI ---
echo "Generating summaries and ranking..."

python3 - << 'PYEOF'
import json
import os
import re
import subprocess
import sys

DATA_DIR = os.environ.get("DATA_DIR", "/home/freet/.openclaw/workspace/sicsicduck/data")

with open(os.path.join(DATA_DIR, "raw_stories.json")) as f:
    stories = json.load(f)

if not stories:
    print("No stories to process")
    sys.exit(1)

# Deduplicate by title similarity
seen_titles = set()
unique = []
for s in stories:
    key = re.sub(r'[^a-z0-9]', '', s["title"].lower())
    if key not in seen_titles:
        seen_titles.add(key)
        unique.append(s)

stories = unique
print(f"After dedup: {len(stories)} stories")

# Chunk for AI processing
def summarize_chunk(chunk, idx, total):
    """Use Kimi API for summarization"""
    titles_text = "\n".join(
        f"{i+1}. [{s['source']}] {s['title']}" for i, s in enumerate(chunk)
    )
    
    prompt = f"""You are a financial news editor. Given these {len(chunk)} news headlines, do three things:

1. For each headline, write a 1-sentence English summary (if the headline is already clear, just rephrase briefly).
2. Assign each a relevance score 1-10 for a Chinese tech/finance audience (10 = most relevant).
3. Return a JSON array of objects with keys: index (1-based), summary, score.

Headlines:
{titles_text}

Return ONLY valid JSON array, no markdown fences:"""

    # Use Kimi API
    api_key = os.environ.get("MOONSHOT_API_KEY", os.environ.get("KIMI_API_KEY", ""))
    if not api_key:
        # Fallback: use headlines directly
        return [{"index": i+1, "summary": s["title"], "score": 5} for i, s in enumerate(chunk)]
    
    try:
        import urllib.request
        data = json.dumps({
            "model": "kimi-k2",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 3000,
        }).encode()
        
        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if present
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            return json.loads(content)
    except Exception as e:
        print(f"  AI summary failed for chunk {idx+1}/{total}: {e}", file=sys.stderr)
        return [{"index": i+1, "summary": s["title"], "score": 5} for i, s in enumerate(chunk)]

# Process in chunks of 15
CHUNK_SIZE = 15
all_results = []
for i in range(0, len(stories), CHUNK_SIZE):
    chunk = stories[i:i+CHUNK_SIZE]
    chunk_num = i // CHUNK_SIZE + 1
    total_chunks = (len(stories) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"  Summarizing chunk {chunk_num}/{total_chunks} ({len(chunk)} stories)...")
    results = summarize_chunk(chunk, chunk_num, total_chunks)
    all_results.extend(results)

# Merge scores back
for i, s in enumerate(stories):
    if i < len(all_results):
        s["summary"] = all_results[i].get("summary", s["title"])
        s["score"] = all_results[i].get("score", 5)
    else:
        s["summary"] = s["title"]
        s["score"] = 5

# Sort by score descending
stories.sort(key=lambda x: x.get("score", 0), reverse=True)

with open(os.path.join(DATA_DIR, "ranked_stories.json"), "w") as f:
    json.dump(stories, f, indent=2, ensure_ascii=False)

print(f"Ranked {len(stories)} stories, top score: {stories[0]['score'] if stories else 'N/A'}")
PYEOF

# --- 3. Build news.html ---
echo "Building news.html..."

python3 - << 'PYEOF'
import json
import os
import html
from datetime import datetime, timezone

DATA_DIR = os.environ.get("DATA_DIR", "/home/freet/.openclaw/workspace/sicsicduck/data")
OUT_PATH = os.environ.get("OUT_PATH", "/home/freet/.openclaw/workspace/sicsicduck/news.html")

with open(os.path.join(DATA_DIR, "ranked_stories.json")) as f:
    stories = json.load(f)

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
top_stories = stories[:20]

def score_color(score):
    if score >= 9: return "#e74c3c"
    if score >= 7: return "#e67e22"
    if score >= 5: return "#f39c12"
    return "#95a5a6"

def score_label(score):
    if score >= 9: return "🔥 HOT"
    if score >= 7: return "📈 Important"
    if score >= 5: return "📰 Notable"
    return "📎 Info"

rows = ""
for i, s in enumerate(top_stories, 1):
    title_e = html.escape(s["title"])
    link = html.escape(s.get("link", "#"))
    summary_e = html.escape(s.get("summary", s["title"]))
    source_e = html.escape(s.get("source", "Unknown"))
    published_e = html.escape(s.get("published", ""))
    score = s.get("score", 5)
    color = score_color(score)
    label = score_label(score)
    
    rows += f"""
        <div class="story">
            <div class="score-badge" style="background:{color}">{score}</div>
            <div class="story-content">
                <div class="story-meta">
                    <span class="source">{source_e}</span>
                    <span class="label">{label}</span>
                    {"<span class='published'>" + published_e + "</span>" if published_e else ""}
                </div>
                <h3><a href="{link}" target="_blank" rel="noopener">{title_e}</a></h3>
                <p>{summary_e}</p>
            </div>
        </div>"""

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🦆 sicsicduck Financial News</title>
<style>
  :root {{
    --bg: #0f1923;
    --card: #1a2634;
    --text: #e8eaed;
    --muted: #8899aa;
    --accent: #4fc3f7;
    --border: #2a3a4a;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
  }}
  header {{
    text-align: center;
    padding: 30px 0 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
  }}
  header h1 {{ font-size: 1.8em; margin-bottom: 6px; }}
  header h1 span {{ color: var(--accent); }}
  .updated {{ color: var(--muted); font-size: 0.85em; }}
  .stats {{
    display: flex;
    justify-content: center;
    gap: 24px;
    margin: 16px 0;
    flex-wrap: wrap;
  }}
  .stat {{
    background: var(--card);
    padding: 10px 20px;
    border-radius: 8px;
    text-align: center;
    border: 1px solid var(--border);
  }}
  .stat-num {{ font-size: 1.5em; font-weight: bold; color: var(--accent); }}
  .stat-label {{ font-size: 0.8em; color: var(--muted); }}
  .story {{
    display: flex;
    gap: 14px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
  }}
  .story:hover {{ border-color: var(--accent); }}
  .score-badge {{
    min-width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.9em;
    color: #fff;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .story-content {{ flex: 1; min-width: 0; }}
  .story-meta {{
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }}
  .source {{
    background: #263238;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75em;
    color: var(--accent);
  }}
  .label {{ font-size: 0.75em; color: var(--muted); }}
  .published {{ font-size: 0.7em; color: var(--muted); }}
  h3 {{ font-size: 1em; margin-bottom: 4px; }}
  h3 a {{ color: var(--text); text-decoration: none; }}
  h3 a:hover {{ color: var(--accent); }}
  p {{ font-size: 0.85em; color: var(--muted); }}
  footer {{
    text-align: center;
    padding: 24px 0;
    color: var(--muted);
    font-size: 0.8em;
    border-top: 1px solid var(--border);
    margin-top: 20px;
  }}
</style>
</head>
<body>
<header>
  <h1>🦆 <span>sicsicduck</span> Financial News</h1>
  <div class="updated">Last updated: {now}</div>
  <div class="stats">
    <div class="stat">
      <div class="stat-num">{len(stories)}</div>
      <div class="stat-label">Total Stories</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len([s for s in stories if s.get('score',0) >= 7])}</div>
      <div class="stat-label">High Priority</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(set(s.get('source','') for s in stories))}</div>
      <div class="stat-label">Sources</div>
    </div>
  </div>
</header>

<main>{rows}</main>

<footer>
  Powered by 🦆 sicsicduck · Auto-generated with AI summaries · {len(stories)} stories from {len(set(s.get('source','') for s in stories))} sources
</footer>
</body>
</html>"""

with open(OUT_PATH, "w") as f:
    f.write(page)

print(f"Written {OUT_PATH} ({len(page)} bytes, {len(top_stories)} stories displayed)")
PYEOF

# --- 4. Git commit and push ---
echo "Committing and pushing..."

git add -A
if git diff --cached --quiet; then
    echo "No changes to commit."
else
    git commit -m "📰 News update: $(date -u '+%Y-%m-%d %H:%M UTC')"
    git push 2>&1 || echo "Push failed (might not have remote configured)"
fi

echo "Done! ✅"
