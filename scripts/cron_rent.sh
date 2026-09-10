#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
[ -f .env ] && export $(grep -v '^#' .env | xargs)
python3 scripts/update_rental_income.py --rent >> /tmp/sicsicduck-rental.log 2>&1
if [ $? -eq 0 ]; then
  echo "💰 租金數據更新完成 ✅"
else
  echo "❌ 租金數據更新失敗，請檢查 /tmp/sicsicduck-rental.log"
  exit 1
fi
