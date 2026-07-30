#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
python3 scripts/update_rates.py >> /tmp/sicsicduck-rate.log 2>&1
if grep -q "23/23 成功" /tmp/sicsicduck-rate.log; then
  openclaw message send --channel telegram -t telegram:885017126 -m "🏦 利率更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 利率更新失敗，請檢查 /tmp/sicsicduck-rate.log" 2>/dev/null
fi
