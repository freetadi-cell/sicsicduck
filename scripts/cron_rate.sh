#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck

# 記錄今次 run 嘅起始行數，只 grep 今次輸出（避免舊 log 殘留造成誤判）
LINES_BEFORE=$(wc -l < /tmp/sicsicduck-rate.log 2>/dev/null || echo 0)
python3 scripts/update_rates.py >> /tmp/sicsicduck-rate.log 2>&1

if tail -n +"$((LINES_BEFORE+1))" /tmp/sicsicduck-rate.log | grep -q "Git commit and push completed"; then
  openclaw message send --channel telegram -t telegram:885017126 -m "🏦 利率更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 利率更新失敗，請檢查 /tmp/sicsicduck-rate.log" 2>/dev/null
fi
