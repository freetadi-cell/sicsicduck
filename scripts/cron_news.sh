#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
python3 scripts/fetch_news.py >> /tmp/sicsicduck-news.log 2>&1
git add -A && git diff --staged --quiet || (git commit -m "Auto: news update $(date '+%Y-%m-%d %H:%M')" && git push origin master)
if [ $? -eq 0 ]; then
  openclaw message send --channel telegram -t telegram:885017126 -m "📰 新聞更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 新聞更新失敗，請檢查 /tmp/sicsicduck-news.log" 2>/dev/null
fi
