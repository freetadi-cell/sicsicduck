#!/bin/bash
# 新聞更新腳本：抓取 → 選篇 → 摘要 → 建頁 → 推送
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck

PUSH_TIMEOUT=60
PUSH_RETRIES=3

# 通知頻率控制
NOTIFY_HOURS=(8 12 17 22)
NOTIFY_NOW=$(date '+%H')
NOTIFY_YES=0
for h in "${NOTIFY_HOURS[@]}"; do
  if [ "$NOTIFY_NOW" -eq "$h" ]; then NOTIFY_YES=1; break; fi
done
export SIC_NEWS_NOTIFY="$NOTIFY_YES"

# 1) 抓取新聞
if ! python3 scripts/fetch_news.py >> /tmp/sicsicduck-news.log 2>&1; then
  echo "❌ 新聞抓取失敗，請檢查 /tmp/sicsicduck-news.log"
  exit 1
fi

# 2) 揀選 top 3
if ! python3 scripts/select_top.py --top 3 --max-per-source 1 >> /tmp/sicsicduck-news.log 2>&1; then
  echo "[cron_news] select_top 失敗" >> /tmp/sicsicduck-news.log
fi

# 3) 摘要
if ! python3 scripts/fetch_article_body.py --all-sources 10 >> /tmp/sicsicduck-news.log 2>&1; then
  echo "[cron_news] 摘要生成失敗（已跳過）" >> /tmp/sicsicduck-news.log
fi

# 4) 重建 news.html
./venv/bin/python3 scripts/build_news_local.py --summary-only >> /tmp/sicsicduck-news.log 2>&1

# 5) 提交變更
git add -A
if git diff --staged --quiet; then
  if [ "$SIC_NEWS_NOTIFY" -eq 1 ]; then
    echo "✅ 新聞更新：無新變更"
  fi
  exit 0
fi
git commit -m "Auto: news update $(date '+%Y-%m-%d %H:%M')" >> /tmp/sicsicduck-news.log 2>&1

# 6) 推送
push_ok=0
for i in $(seq 1 $PUSH_RETRIES); do
  if timeout $PUSH_TIMEOUT git push origin master >> /tmp/sicsicduck-news.log 2>&1; then
    push_ok=1; break
  fi
  echo "[cron_news] push 第 ${i} 次失敗，重試中..." >> /tmp/sicsicduck-news.log
  sleep 5
done

# 7) 通知
if [ "$push_ok" -eq 1 ]; then
  if [ "$SIC_NEWS_NOTIFY" -eq 1 ]; then
    echo "📰 新聞更新完成 ✅"
  fi
else
  echo "❌ 新聞推送失敗（重試 ${PUSH_RETRIES} 次），請檢查 /tmp/sicsicduck-news.log"
  exit 1
fi
