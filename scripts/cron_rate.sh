#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
[ -f .env ] && export $(grep -v '^#' .env | xargs)

# 記錄今次 run 嘅起始行數，只 grep 今次輸出（避免舊 log 殘留造成誤判）
LINES_BEFORE=$(wc -l < /tmp/sicsicduck-rate.log 2>/dev/null || echo 0)
python3 scripts/update_rates.py >> /tmp/sicsicduck-rate.log 2>&1
