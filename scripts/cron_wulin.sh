#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
[ -f .env ] && export $(grep -v '^#' .env | xargs)

python3 scripts/update_wulin.py >> /tmp/sicsicduck-wulin.log 2>&1
if [ $? -eq 0 ]; then
  echo "⚔️ 武林世界推進完成 ✅"
else
  echo "❌ 武林世界推進失敗，請檢查 /tmp/sicsicduck-wulin.log"
  exit 1
fi
