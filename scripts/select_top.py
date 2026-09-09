#!/usr/bin/env python3
"""
select_top.py — 從 news.json 揀出最火熱 N 篇置頂，同一來源唔多於 M 篇。

揀中嘅文章標記 pinned=True 並移到最前，其餘保留唔刪。

用法：
    python3 scripts/select_top.py              # 預設 top 3, 每源最多 3
    python3 scripts/select_top.py --top 5 --max-per-source 2
    python3 scripts/select_top.py --dry-run     # 只打印，唔寫檔
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"
NEWS_FILE = DATA_DIR / "news.json"

# ---- 新聞價值評分（同 fetch_news.py 一致）----
_HIGH_VALUE_KW = [
    "股", "市", "恒指", "恆指", "美股", "港股", "nasdaq", "dow", "利率", "利息", "加息", "減息",
    "債", "國債", "美債", "聯儲", "儲局", "通脹", "央行", "匯率", "美元", "港元",
    "金價", "黃金", "石油", "原油", "油價",
    "樓", "地產", "物業", "按揭", "租金", "發展商",
    "ipo", "上市", "停牌", "私有化", "回購", "派息", "股息",
    "基金", "etf", "投資", "理財", "證券",
    "特朗普", "美國", "中國", "日本", "歐盟", "俄羅斯", "烏克蘭",
    "戰爭", "制裁", "關稅", "貿易戰", "地緣",
    "联合国", "聯合國", "北約", "nato",
    "晶片", "半導體", "nvidia", "輝達", "蘋果", "微軟", "谷歌", "ai", "人工智能",
    "電動車", "比亞迪", "tesla", "新能源",
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
    title = str(article.get("title") or "").lower()
    desc = str(article.get("description") or "").lower()
    text = title + " " + desc
    source = str(article.get("source_name") or "").lower()

    score = 40
    bonus = 0
    for kw in _HIGH_VALUE_KW:
        if kw.lower() in text:
            bonus += 15
    score += min(bonus, 60)
    for kw in _LOW_VALUE_KW:
        if kw.lower() in text:
            score -= 20
    if "finance" in source or "經濟" in source or "yahoo" in source:
        score += 15
    if source == "cnn":
        score += 10
    title_len = len(str(article.get("title") or ""))
    if 20 <= title_len <= 80:
        score += 5
    return max(0, min(100, score))


def select_top(articles, top_n=3, max_per_source=1):
    """按分數排序，逐篇揀入，置頂文章來自唔同來源。"""
    scored = [(news_value_score(a), i, a) for i, a in enumerate(articles)]
    scored.sort(key=lambda x: (-x[0], x[1]))  # 分數高優先，同分按原序

    selected_ids = set()
    source_count = {}
    for score, orig_i, a in scored:
        src = a.get("source_name", "unknown")
        if source_count.get(src, 0) >= max_per_source:
            continue
        selected_ids.add(id(a))
        source_count[src] = source_count.get(src, 0) + 1
        a["_score"] = score
        if len(selected_ids) >= top_n:
            break
    return selected_ids


def main():
    top_n = 3
    max_per_source = 1
    dry_run = "--dry-run" in sys.argv

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--top" and i < len(sys.argv) - 1:
            top_n = int(sys.argv[i + 1])
        if arg == "--max-per-source" and i < len(sys.argv) - 1:
            max_per_source = int(sys.argv[i + 1])

    if not NEWS_FILE.exists():
        print("[select_top] news.json 不存在")
        return

    with open(NEWS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    articles = data.get("articles", [])
    print(f"[select_top] 共 {len(articles)} 篇候選")

    # 先清走舊嘅 pinned 標記
    for a in articles:
        a.pop("pinned", None)
        a.pop("_score", None)

    selected_ids = select_top(articles, top_n, max_per_source)
    print(f"[select_top] 揀中 {len(selected_ids)} 篇置頂（每源最多 {max_per_source} 篇）")

    # 分兩組：置頂（按分數排序）+ 其餘（保持原序）
    pinned = []
    rest = []
    for a in articles:
        if id(a) in selected_ids:
            a["pinned"] = True
            pinned.append(a)
            src = a.get("source_name", "?")
            score = a.get("_score", "?")
            title = a.get("title", "")[:50]
            print(f"  🔝 [{score}] ({src}) {title}")
        else:
            rest.append(a)

    if dry_run:
        print(f"[select_top] DRY-RUN，唔寫檔（{len(pinned)} 置頂 + {len(rest)} 其餘）")
        return

    # 置頂放最前，其餘保持原序
    all_articles = pinned + rest

    # 清走 _score
    for a in all_articles:
        a.pop("_score", None)

    data["articles"] = all_articles
    data["total"] = len(all_articles)
    data["last_updated"] = datetime.now().isoformat()
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[select_top] ✅ {len(pinned)} 篇置頂 + {len(rest)} 篇其餘，共 {len(all_articles)} 篇")


if __name__ == "__main__":
    main()
