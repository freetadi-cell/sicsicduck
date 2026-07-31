#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
python3 scripts/update_rental_income.py --all >> /tmp/sicsicduck-rental.log 2>&1
if [ $? -eq 0 ]; then
  git add data/rental_income.json && git diff --staged --quiet || (git commit -m "Auto: rental income update $(date '+%Y-%m-%d %H:%M')" && git push origin master)
  openclaw message send --channel telegram -t telegram:885017126 -m "🏠 租金回報率更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 租金回報率更新失敗，請檢查 /tmp/sicsicduck-rental.log" 2>/dev/null
fi
