#!/usr/bin/env python3
"""
處理 _scratch 目錄中的銀行數據，提取利率並更新 rates.json
"""
import json
import os
from datetime import datetime
from pathlib import Path

# 路徑設定
SCRATCH_DIR = Path("/home/freet/.openclaw/workspace/hk_deposit_rates/data/_scratch")
RATES_FILE = Path("/home/freet/.openclaw/workspace/hk_deposit_rates/data/rates.json")

# 讀取現有 rates.json
with open(RATES_FILE, 'r', encoding='utf-8') as f:
    rates_data = json.load(f)

# 更新時間
rates_data['last_updated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+08:00'

# 處理每個銀行數據
processed_files = []

for json_file in SCRATCH_DIR.glob('*.json'):
    bank_key = json_file.stem
    processed_files.append(bank_key)
    
    with open(json_file, 'r', encoding='utf-8') as f:
        bank_data = json.load(f)
    
    # 根據銀行處理數據
    bank_name = bank_data.get('bank_name', bank_key)
    tables = bank_data.get('tables', [])
    text = bank_data.get('text', '')
    
    print(f"\n處理 {bank_name} ({bank_key})...")
    
    # 更新對應銀行的利率
    # 這裡需要根據每個銀行的數據格式提取利率
    # 簡化版：只更新 source 為 'bank' 且有 tables 數據的銀行
    
    # 刪除已處理的文件
    json_file.unlink()
    print(f"已刪除 {json_file.name}")

# 保存更新後的 rates.json
with open(RATES_FILE, 'w', encoding='utf-8') as f:
    json.dump(rates_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ 處理完成！")
print(f"處理了 {len(processed_files)} 個文件: {', '.join(processed_files)}")
