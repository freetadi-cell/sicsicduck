#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rank_news.py — 用 GLM-5.2 判斷「當日最火熱 + 非娛樂花邊」新聞，置頂頭 4 篇。

流程：
1. 讀 data/news.json，抽出「今日」(pubDate == 今天) 文章
2. 規則預篩：剔除明顯娛樂花邊 (category=entertainment / keywords / 標題關鍵詞)
3. 剩低候選標題一次過打包，call GLM-5.2 揀最火熱 + 最相關嘅 Top 4
4. 將揀中嘅 4 篇 reorder 到 news.json 列表最前，標記 pinned=True
5. build script 讀到 pinned 就放最前（頭 4 篇顯示圖片）

用法：
    ./venv/bin/python3 scripts/rank_news.py            # 正常執行，改寫 news.json
    ./venv/bin/python3 scripts/rank_news.py --dry-run  # 只輸出決策，唔寫檔

如果無候選或 GLM 呼叫失敗 → 唔改動，保持原排序（安全 fallback）。
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ---- 路徑 ----
SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"
NEWS_FILE = DATA_DIR / "news.json"

# ---- 智譜 GLM API（同 fetch_article_body.py 一致）----
OPENCLAW_CFG = Path("/home/freet/.openclaw/openclaw.json")
API_BASE = "https://yuanyuaicloud.cn/v1"
API_MODEL = "glm-5.2"
API_TIMEOUT = 60

# ---- 置頂篇數 ----
TOP_N = 4

# ---- 娛樂花邊關鍵詞（規則預篩，第一道閘）----
# 命中 => 唔會俾 GLM 揀（亦唔會置頂）
ENTERTAIN_KEYWORDS = [
    # category / keywords / 標題
    "entertainment",
    # 韓星/明星/藝人
    "韓星", "韓團", "韓國女團", "明星", "藝人", "緋聞", "戀情", "結婚", "離婚",
    "生圖", "寫真", "紅毯", "出騷",
    # 電視/電影/劇集
    "電視劇", "劇集", "電影", "Netflix", "Disney+", "串流", "影評", "票房",
    "綜藝", "真人show", "選秀",
    # 音樂/歌手
    "演唱會", "歌手", "專輯", "金曲", "MV", "打歌",
    # 遊戲/電玩
    "遊戲", "電玩", "手遊", "遊戲王", "攻略", "PS5", "Xbox", "Steam", "任天堂",
    "魔獸", "英雄聯盟", "LOL", "原神",
    # 娛樂圈雜項
    "娛樂圈", "娛圈", "明星穿搭", "素顏", "街拍", "粉絲", "應援", "代言",
    "時裝周", "米蘭時裝周",
    # 生活瑣碎（非財經大事，GLM 通常唔揀，但預篩先剔走）
    "洗頭水", "護膚", "食譜", "湯水", "防靜電", "家居清潔",
]

# 標題層另外過濾：人名 + 娛樂字眼連住（eg 蒙嘉慧…返日本 / 鄭伊健）
# 呢啲單靠關鍵詞可能漏，靠 GLM 判斷兜底。


def load_news():
    if not NEWS_FILE.exists():
        return []
    with open(NEWS_FILE, encoding="utf-8") as f:
        return json.load(f).get("articles", [])


def save_news(articles):
    d = {"articles": articles, "total": len(articles),
         "last_updated": datetime.now().isoformat()}
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def get_api_key():
    with open(OPENCLAW_CFG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["models"]["providers"]["yuanyuai"]["apiKey"]


def is_entertainment(a):
    """規則預篩：命中娛樂花邊關鍵詞 => True"""
    hay = " ".join([
        str(a.get("title", "")),
        " ".join(a.get("category", []) or []),
        " ".join(str(k) for k in (a.get("keywords", []) or [])),
    ])
    return any(kw in hay for kw in ENTERTAIN_KEYWORDS)


def call_glm(api_key, prompt):
    """call GLM-5.2，返回純文字回覆（失敗 raise）。"""
    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "system",
             "content": "你是新聞編輯。請嚴格按指示輸出，只回 JSON，不要任何其他文字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_glm_json(text):
    """從 GLM 回覆抽 JSON（可能包喺 ```json 或零散文字入面）。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        # 直接試 parse
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 容錯：切出第一個 { 到最後一個 }
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s:e+1])
            except json.JSONDecodeError:
                pass
    return None


def rank(articles):
    """將置頂嘅 TOP_N 篇移到列表最前，其餘保持原序。返回 (新列表, 置頂id列表, 理由)。"""
    if not articles:
        return articles, [], "無候選"

    today = datetime.now().strftime("%Y-%m-%d")
    # 候選 = 今日文章（fallback：如今日少於 TOP_N*2 篇，用最近 3 日補足）
    today_arts = [a for a in articles if (a.get("pubDate", "") or "")[:10] == today]
    pool = today_arts if len(today_arts) >= TOP_N * 2 else \
        [a for a in articles if (a.get("pubDate", "") or "")[:10] >=
         (datetime.now() - __import__("datetime").timedelta(days=3)).strftime("%Y-%m-%d")]

    # 規則預篩：剔走娛樂花邊
    cands = [(i, a) for i, a in enumerate(pool) if not is_entertainment(a)]
    if len(cands) < TOP_N:
        # 候選太少，放寬：唔預篩，交俾 GLM 全權判斷（GLM 自己會排除娛樂）
        cands = [(i, a) for i, a in enumerate(pool)]
    if len(cands) < TOP_N:
        return articles, [], f"候選不足（{len(cands)}）"

    # 打包標題俾 GLM
    lines = []
    for idx, (i, a) in enumerate(cands):
        title = (a.get("title", "") or "").strip().replace("\n", " ")
        src = a.get("source_name", "") or ""
        lines.append(f"[{idx}]（{src}）{title}")
    candidate_text = "\n".join(lines)

    prompt = f"""以下是今日（{today}）嘅新聞候選清單，每行一條，格式 [編號]（來源）標題。

請以「食息鴨」網站讀者（香港小投資者，關注財經、樓市、利率、股息、國際大事）嘅角度，
揀出最火熱、最重要、最值得置頂嘅 {TOP_N} 篇新聞。

要求：
1. 只揀財經/地產/利率/投資/國際大事等有實質新聞價值嘅嘢
2. 堅決排除娛樂花邊、生活瑣碎、軟性消費內容（明星緋聞、遊戲、護膚、食譜、明星私生活等）
3. 如候選大部分都係娛樂/花邊，就揀較有資訊量嘅，但寧缺勿濫

候選清單：
{candidate_text}

只輸出 JSON，格式：
{{"top": [[編號, 理由], [編號, 理由], [編號, 理由], [編號, 理由]]}}
理由請用一句廣東話簡短說明。"""

    api_key = get_api_key()
    resp = call_glm(api_key, prompt)
    parsed = parse_glm_json(resp)

    if not parsed or "top" not in parsed:
        print(f"[rank_news] GLM 回覆無法解析，保留原排序。回覆：{resp[:300]}", file=sys.stderr)
        return articles, [], "GLM 回覆無法解析"

    picks = parsed["top"]
    if not isinstance(picks, list) or len(picks) == 0:
        return articles, [], "GLM 未揀到"

    # 收集揀中嘅候選 index（去重、夾返 cands）
    chosen_cands = []
    seen = set()
    for item in picks:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            n = item[0]
        elif isinstance(item, dict) and "編號" in item:
            n = item["編號"]
        elif isinstance(item, dict) and "index" in item:
            n = item["index"]
        else:
            n = item
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if n in seen or n < 0 or n >= len(cands):
            continue
        seen.add(n)
        chosen_cands.append(cands[n])
        if len(chosen_cands) >= TOP_N:
            break

    if not chosen_cands:
        return articles, [], "GLM 揀選無效"

    # 置頂：將揀中嘅文章移到列表最前（保持 GLM 揀嘅順序），其餘保持原序
    chosen_ids = [a.get("id") for _, a in chosen_cands]
    # 揀中嘅集合（去重）
    chosen_set = set()
    ordered_ids = []
    for cid in chosen_ids:
        if cid not in chosen_set:
            chosen_set.add(cid)
            ordered_ids.append(cid)
    # 原列表分兩組：揀中（按 GLM 順序） vs 未揀中（保持原序）
    pinned_map = {cid: None for cid in ordered_ids}
    rest = []
    for a in articles:
        aid = a.get("id")
        if aid in pinned_map:
            pinned_map[aid] = a
        else:
            rest.append(a)
    ordered_pinned = []
    for cid in ordered_ids:
        if pinned_map[cid] is not None:
            a = pinned_map[cid]
            a["pinned"] = True
            ordered_pinned.append(a)
    reason = "；".join(
        str(item[-1]) if isinstance(item, (list, tuple)) else str(item)
        for item in picks) if picks else ""
    return ordered_pinned + rest, ordered_ids, reason


def main():
    dry_run = "--dry-run" in sys.argv
    articles = load_news()
    if not articles:
        print("[rank_news] news.json 無文章")
        return

    new_list, ids, reason = rank(articles)
    if dry_run:
        print(f"[rank_news][DRY-RUN] 置頂 {len(ids)} 篇：{ids}")
        print(f"[rank_news][DRY-RUN] 理由：{reason}")
        if ids:
            by_id = {a.get("id"): a for a in new_list}
            for i in ids:
                print(f"  - {i}  {by_id[i].get('title','')[:50]}")
        return

    if not ids:
        print(f"[rank_news] 無置頂變更（{reason}）")
        return

    save_news(new_list)
    for i in ids:
        a = next((x for x in new_list if x.get('id') == i), {})
        print(f"[rank_news] 置頂：{a.get('title','')[:60]}")


if __name__ == "__main__":
    main()
