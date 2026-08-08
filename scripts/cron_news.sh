#!/bin/bash
# 新聞更新腳本：抓取 -> 提交 -> 推送（含 timeout + 重試）-> 發通知
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck

PUSH_TIMEOUT=60     # 單次 push 最長秒數
PUSH_RETRIES=3      # push 重試次數

# 1) 抓取新聞
if ! python3 scripts/fetch_news.py >> /tmp/sicsicduck-news.log 2>&1; then
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 新聞抓取失敗，請檢查 /tmp/sicsicduck-news.log" 2>/dev/null
  exit 1
fi

# 1.5) 為新抓取嘅新聞寫摘要（RSS + newsdata.io，含 GLM 改寫，失敗不阻斷主流程）
# 只處理近期新文章，每輪最多 25 篇，避免 quota 用罄（BATCH_LIMIT 可透過數字參數覆蓋）
if ! python3 scripts/fetch_article_body.py --all-sources 25 >> /tmp/sicsicduck-news.log 2>&1; then
  echo "[cron_news] 摘要生成失敗（已跳過，不阻塞部署）" >> /tmp/sicsicduck-news.log
fi

# 1.6) 淨化 news.json：只保留有摘要(rewritten)嗰啲文章，冇摘要嘅移除（唔堆返幾千篇落 cache）
SHOWN=$(grep -c 'class="article-card"' news.html)
python3 - <<'EOF' >> /tmp/sicsicduck-news.log 2>&1
import json, os
path = "data/news.json"
d = json.load(open(path, encoding="utf-8"))
arts = d.get("articles", [])
kept = []
for a in arts:
    p = f"articles_cache/{a.get('id','')}.json"
    if os.path.exists(p):
        try:
            c = json.load(open(p, encoding="utf-8"))
            if c.get("status") == "done" and c.get("rewritten"):
                kept.append(a)
        except Exception:
            pass
removed = len(arts) - len(kept)
if removed > 0:
    d["articles"] = kept
    d["total"] = len(kept)
    d["last_updated"] = __import__("datetime").datetime.now().isoformat()
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[purge] 移除 {removed} 篇冇摘要，保留 {len(kept)} 篇")
EOF

# 1.7) 重建 news.html（只顯示有摘要嘅文章）——唔重新抓取
python3 scripts/build_news_local.py --summary-only >> /tmp/sicsicduck-news.log 2>&1

# 2) 提交變更（無變更則跳過）
git add -A
if git diff --staged --quiet; then
  openclaw message send --channel telegram -t telegram:885017126 -m "✅ 新聞更新：無新變更" 2>/dev/null
  exit 0
fi
git commit -m "Auto: news update $(date '+%Y-%m-%d %H:%M')" >> /tmp/sicsicduck-news.log 2>&1

# 3) 推送（帶 timeout + 重試）
push_ok=0
for i in $(seq 1 $PUSH_RETRIES); do
  if timeout $PUSH_TIMEOUT git push origin master >> /tmp/sicsicduck-news.log 2>&1; then
    push_ok=1
    break
  fi
  echo "[cron_news] push 第 ${i} 次失敗，重試中..." >> /tmp/sicsicduck-news.log
  sleep 5
done

# 4) 發通知
if [ "$push_ok" -eq 1 ]; then
  openclaw message send --channel telegram -t telegram:885017126 -m "📰 新聞更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 新聞已抓取但推送失敗（已重試 ${PUSH_RETRIES} 次），請檢查 /tmp/sicsicduck-news.log" 2>/dev/null
  exit 1
fi
