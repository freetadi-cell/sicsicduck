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
