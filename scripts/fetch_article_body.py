#!/usr/bin/env python3
"""
為 RSS 新聞抓正文 + 智譜 GLM-5.2 改寫，暫存本地 articles_cache/。

版權原則：只存「自撰摘要」(rewritten)，不存原文全文。
每篇 <id>.json:
  {
    "id", "title", "source_name", "link",
    "rewritten": 自撰摘要(≤200字),
    "status": "done" | "no_body" | "rewrite_failed" | "paid_wall",
    "fetched_at": ISO
  }
"""
import json, re, sys, time, urllib.request, hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "articles_cache"
NEWS_FILE = DATA_DIR / "news.json"

# 智譜 API key 從 openclaw.json models.providers.yuanyuai 提取
OPENCLAW_CFG = Path("/home/freet/.openclaw/openclaw.json")
API_BASE = "https://yuanyuaicloud.cn/v1"
API_MODEL = "glm-5.2"

UA = ("Mozilla/5.0 (compatible; SicsicDuck/1.0; +https://sicsicduck.com) "
      "AppleWebKit/537.36")

# 每篇改寫目標字數（版權安全底線：不超過 200 字自撰摘要）
MAX_SUMMARY_CHARS = 200
# 每輪最多處理幾篇（避免大量請求）；傳 0 表示無上限，全部處理
BATCH_LIMIT = 0
for _a in sys.argv[1:]:
    if _a.isdigit():
        BATCH_LIMIT = int(_a)
        break
if BATCH_LIMIT and BATCH_LIMIT > 0:
    print(f"每輪限處理 {BATCH_LIMIT} 篇（傳 0 可無上限）")
# 只處理過去幾多天之內的文章
RECENT_DAYS = 3
# 兩個 API 請求間隔（秒），避免過密
API_DELAY = 0.5


def get_api_key():
    with open(OPENCLAW_CFG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["models"]["providers"]["yuanyuai"]["apiKey"]


def load_news():
    if not NEWS_FILE.exists():
        return []
    with open(NEWS_FILE, encoding="utf-8") as f:
        return json.load(f).get("articles", [])


def load_cache(article_id):
    p = CACHE_DIR / f"{article_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def save_cache(entry):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"{entry['id']}.json"
    p.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 正文抽取 ----------
PAY_WALL_HINTS = ["登入以繼續", "請登入", "會員計劃", "立即訂閱", "log in to read",
                  "subscribe to read", "全文只限會員", "付費內容"]


def extract_body(url, html):
    """用 bs4 抽取正文純文字（hkej/rthk/scmp 通用），返回截斷正文。"""
    soup = BeautifulSoup(html, "html.parser")

    # 逐 tag 拆掉 menu / nav / header / footer / script / style / 廣告
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "form", "button", "iframe", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    body = "\n".join(lines)

    # 檢查是否付費牆
    if any(h in body for h in PAY_WALL_HINTS) and len(body) < 400:
        return None  # 代表付費牆，無正文

    # 截斷，避免傳成噸文字畀 API（也避免過度使用原文）
    if len(body) > 4000:
        body = body[:4000]
    return body


def fetch_body(url):
    """抓正文。成功回傳字串，失敗回傳 None（及原因）。"""
    host = urlparse(url).netloc.lower()
    try:
        r = requests.get(url, headers={
            "User-Agent": UA,
            "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        }, timeout=25)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and r.text.lstrip()[:1] not in ("<",):
            # 可能係 JSON/NON-HTML
            return None
        body = extract_body(url, r.text)
        return body if body and len(body) > 60 else None
    except Exception as e:
        print(f"    [fetch] 失敗 {host}: {e}", file=sys.stderr)
        return None


# ---------- 智譜 API 改寫 ----------
def rewrite_with_glm(api_key, title, body):
    sys_prompt = ("你係專業中文新聞編輯，負責將原媒體新聞改寫成自家版本嘅標題同摘要，避免逐字照抄原媒體（版權問題）。\n"
                  "【語言要求】必須使用繁體中文（香港／台灣用字，如『資訊、支援、網絡、程式、股價』等），"
                  "絕不可輸出簡體字。\n"
                  "【標題要求】將原標題改寫為一句自己嘅講法（約 20-30 字）：\n"
                  "  - 保留新聞事實：人名（特朗普、李聲揚等）、數字、地點、公司名一定要留\n"
                  "  - 保留關鍵詞用嚟搜尋分類：樓市、利率、股市、美匯、金價、地產等字眼要留住\n"
                  "  - 唔逐字照搬原標題，換措辭重新組織\n"
                  "  - 唔好改成 clickbait 或誇大失真，客觀持平\n"
                  "【摘要要求】將新聞正文改寫為一段約"
                  f"{MAX_SUMMARY_CHARS}字以內嘅中文摘要。\n"
                  "  - 用你自己嘅措辭重新組織，不得逐字複製原文句子\n"
                  "  - 客觀陳述事實，保留必要數字、公司名、人名\n"
                  "  - 唔好加個人評論，唔好加『以下係』『總結嚟講』等套話\n"
                  "【輸出格式】只輸出 JSON，唔好加任何其他文字：\n"
                  "  {\"title\": \"改寫後標題\", \"summary\": \"改寫後摘要\"}")
    user_prompt = f"原新聞標題:{title}\n\n原新聞正文:\n{body}"

    payload = json.dumps({
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 700,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


# ---------- 主流程 ----------
def main():
    api_key = get_api_key()
    articles = load_news()
    print(f"news.json 共 {len(articles)} 篇")

    # 只挑 RSS 來源（香港經濟日報 / rthk / scmp 等本地來源）
    rss_sources = {"香港經濟日報", "香港電台",
                   "South China Morning Post", "SCMP"}
    # --all-sources 模式：連同 newsdata.io 來源（Yahoo/明報/東網等）都處理
    all_sources = "--all-sources" in sys.argv or "-a" in sys.argv
    # --newsdata-only 模式：淨係處理 newsdata.io 來源（唔理 RSS）
    newsdata_only = "--newsdata-only" in sys.argv or "-n" in sys.argv
    # --force 模式：忽略已有 cache，強制重寫所有候選文章
    force = "--force" in sys.argv or "-f" in sys.argv
    recent = datetime.now().timestamp() - RECENT_DAYS * 86400

    candidates = []
    for a in articles:
        src = a.get("source_name", "")
        pub = a.get("pubDate", "")
        if newsdata_only:
            if src in rss_sources:
                continue  # 淨係 newsdata 來源
        elif not all_sources and src not in rss_sources:
            continue
        # 只處理近期文章
        if pub:
            try:
                ts = datetime.strptime(pub[:19], "%Y-%m-%d %H:%M:%S").timestamp()
                if ts < recent:
                    continue
            except ValueError:
                pass
        if not force:
            cached = load_cache(a.get("id", ""))
            if cached and cached.get("status") == "done":
                continue  # 已有改寫成果
        if not a.get("link"):
            continue
        candidates.append(a)

    print(f"需處理候選 {len(candidates)} 篇")
    if BATCH_LIMIT > 0:
        print(f"（取頭 {BATCH_LIMIT} 篇）")
        candidates = candidates[:BATCH_LIMIT]

    done = no_body = failed = 0
    for i, a in enumerate(candidates, 1):
        aid = a["id"]
        title = a.get("title", "")
        link = a.get("link", "")
        src = a.get("source_name", "")
        print(f"\n[{i}/{len(candidates)}] {title[:40]}... ({src})")

        cached = load_cache(aid)
        if cached and cached.get("status") in ("no_body", "rewrite_failed"):
            # 短時間內唔重試同一失敗
            ago = (datetime.now() -
                   datetime.fromisoformat(cached["fetched_at"])).total_seconds()
            if ago < 3600 * 6:
                print("    最近失敗過，跳過")
                continue

        body = fetch_body(link)
        if not body:
            entry = {
                "id": aid, "title": title, "source_name": src, "link": link,
                "rewritten": "",
                "status": "no_body",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_cache(entry)
            no_body += 1
            print("    ⚠️ 無正文（可能付費牆），跳過")
            continue

        try:
            out = rewrite_with_glm(api_key, title, body)
            # 解析 JSON：{title, summary}
            rewritten_title, rewritten = title, None
            try:
                parsed = json.loads(out.strip())
                if isinstance(parsed, dict):
                    rewritten_title = (parsed.get("title") or title).strip()
                    rewritten = (parsed.get("summary") or "").strip()
            except json.JSONDecodeError:
                # 兼容舊版：直接當摘要
                rewritten = out.strip()
            if not rewritten:
                raise ValueError("GLM 冇回摘要")
            if len(rewritten) > MAX_SUMMARY_CHARS + 50:
                rewritten = rewritten[:MAX_SUMMARY_CHARS] + "…"
            entry = {
                "id": aid, "title": title, "source_name": src, "link": link,
                "rewritten_title": rewritten_title,
                "rewritten": rewritten,
                "status": "done",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_cache(entry)
            done += 1
            print(f"    ✅ 改寫成功 (標題+{len(rewritten)}字摘要)")
        except Exception as e:
            entry = {
                "id": aid, "title": title, "source_name": src, "link": link,
                "rewritten": "",
                "status": "rewrite_failed",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_cache(entry)
            failed += 1
            print(f"    ❌ 改寫失敗: {e}", file=sys.stderr)

        time.sleep(API_DELAY)

    print(f"\n=== 完成: 成功 {done} / 無正文 {no_body} / 失敗 {failed} ===")


if __name__ == "__main__":
    main()
