#!/usr/bin/env python3
"""
測試實際的銀行網站爬取
"""

import json
import os
import sys
import time
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_agent_browser_basic():
    """測試 agent-browser 基本功能"""
    print("測試 agent-browser 基本功能...")
    
    try:
        # 測試打開一個簡單的頁面
        result = subprocess.run(
            'agent-browser open "https://example.com" --timeout 10000',
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            print("  ✅ agent-browser 可以正常打開網頁")
            
            # 獲取頁面標題
            result = subprocess.run(
                'agent-browser get title',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"  頁面標題: {result.stdout.strip()}")
            
            # 關閉瀏覽器
            subprocess.run('agent-browser close', shell=True, capture_output=True, timeout=5)
            return True
        else:
            print(f"  ❌ agent-browser 失敗: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ 測試失敗: {e}")
        return False

def test_bank_scrape_simulation():
    """模擬銀行網站爬取（不使用實際瀏覽器）"""
    print("\n模擬銀行網站爬取測試...")
    
    # 模擬的銀行數據
    mock_bank_data = {
        '滙豐銀行': {
            'hkd': {
                '1m': {'rate': 2.1, 'min_deposit': 10000, 'note': '新資金網上辦理', 'source': 'bank'},
                '3m': {'rate': 2.3, 'min_deposit': 10000, 'note': '新資金網上辦理', 'source': 'bank'},
                '6m': {'rate': 2.2, 'min_deposit': 10000, 'note': '新資金網上辦理', 'source': 'bank'},
            },
            'usd': {
                '3m': {'rate': 3.5, 'min_deposit': 2000, 'note': '新資金網上辦理', 'source': 'bank'},
                '6m': {'rate': 3.4, 'min_deposit': 2000, 'note': '新資金網上辦理', 'source': 'bank'},
            }
        },
        '中銀香港': {
            'hkd': {
                '3m': {'rate': 2.1, 'min_deposit': 10000, 'note': '新資金網上/手機銀行辦理', 'source': 'bank'},
                '6m': {'rate': 1.9, 'min_deposit': 10000, 'note': '新資金網上/手機銀行辦理', 'source': 'bank'},
            }
        }
    }
    
    print("模擬數據結構:")
    for bank_name, currencies in mock_bank_data.items():
        print(f"  {bank_name}:")
        for currency, periods in currencies.items():
            print(f"    {currency.upper()}:")
            for period, data in periods.items():
                print(f"      {period}: {data['rate']}% (最低存款: {data['min_deposit']})")
    
    return mock_bank_data

def test_update_logic():
    """測試更新邏輯"""
    print("\n測試更新邏輯...")
    
    # 加載當前數據
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    rates_file = os.path.join(data_dir, 'rates.json')
    
    if not os.path.exists(rates_file):
        print("  ❌ rates.json 不存在")
        return
    
    with open(rates_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"  當前有 {len(data.get('banks', []))} 間銀行數據")
    
    # 模擬更新一間銀行
    mock_data = test_bank_scrape_simulation()
    
    # 檢查更新邏輯
    banks_to_update = ['滙豐銀行', '中銀香港']
    updated_count = 0
    
    for bank in data.get('banks', []):
        if bank['name'] in banks_to_update and bank['name'] in mock_data:
            print(f"\n  模擬更新 {bank['name']}:")
            
            # 模擬更新 HKD 利率
            if 'hkd' in mock_data[bank['name']]:
                for period, new_rate in mock_data[bank['name']]['hkd'].items():
                    if period in bank['hkd']:
                        old_rate = bank['hkd'][period].get('rate')
                        new_rate_val = new_rate['rate']
                        
                        if old_rate != new_rate_val:
                            print(f"    {period}: {old_rate}% -> {new_rate_val}%")
                            updated_count += 1
                        else:
                            print(f"    {period}: 保持 {old_rate}%")
    
    print(f"\n  總共模擬更新了 {updated_count} 個利率")

def main():
    print("=" * 50)
    print("銀行網站爬取測試")
    print("=" * 50)
    
    # 測試 agent-browser
    browser_ok = test_agent_browser_basic()
    
    if browser_ok:
        print("\n✅ agent-browser 測試通過")
    else:
        print("\n⚠️ agent-browser 測試失敗，將使用後備數據源")
    
    # 測試更新邏輯
    test_update_logic()
    
    print("\n" + "=" * 50)
    print("測試完成")
    print("=" * 50)
    
    if browser_ok:
        print("\n建議：")
        print("1. 腳本已準備好從銀行官網直接獲取數據")
        print("2. 如果 agent-browser 失敗，將自動使用 MoneyHero 後備數據")
        print("3. 運行完整更新: python3 scripts/update_rates.py")
    else:
        print("\n警告：")
        print("1. agent-browser 可能未正確安裝或配置")
        print("2. 腳本將主要依賴 MoneyHero 後備數據")
        print("3. 建議檢查 agent-browser 安裝: npm install -g agent-browser")

if __name__ == '__main__':
    main()