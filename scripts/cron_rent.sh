#!/bin/bash
cd /home/freet/.openclaw/workspace/sicsicduck
python3 scripts/update_rental_income.py --rent >> /tmp/sicsicduck-rental.log 2>&1
if [ $? -eq 0 ]; then
  openclaw message send --channel telegram -t telegram:885017126 -m "💰 租金數據更新完成 ✅" 2>/dev/null
else
  openclaw message send --channel telegram -t telegram:885017126 -m "❌ 租金數據更新失敗，請檢查 /tmp/sicsicduck-rental.log" 2>/dev/null
fi
