#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
[ -f .env ] && export $(grep -v '^#' .env | xargs)
python3 scripts/update_rental_income.py --all >> /tmp/sicsicduck-rental.log 2>&1
if [ $? -eq 0 ]; then
  git add data/rental_income.json && git diff --staged --quiet || (git commit -m "Auto: rental income update $(date '+%Y-%m-%d %H:%M')" && git push origin master)
  echo "🏠 租金回報率更新完成 ✅"
else
  echo "❌ 租金回報率更新失敗，請檢查 /tmp/sicsicduck-rental.log"
  exit 1
fi
