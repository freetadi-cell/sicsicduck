#!/usr/bin/env python3
"""
測試更新腳本
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from update_rates import (
    fetch_url,
    extract_min_deposit,
    extract_note,
    parse_rates_from_text,
    BANK_URLS
)

def test_functions():
    """測試各個函數"""
    print("測試 extract_min_deposit:")
    test_cases = [
        "最低存款10,000港元",
        "起存金額5000港幣",
        "10000港元或以上",
        "5000美元起",
        "min. 10000 hkd",
    ]
    
    for test in test_cases:
        result = extract_min_deposit(test)
        print(f"  '{test}' -> {result}")
    
    print("\n測試 extract_note:")
    test_text = "新資金網上辦理優惠利率"
    result = extract_note(test_text, "滙豐銀行", "hkd", "3m")
    print(f"  '{test_text}' -> '{result}'")
    
    print("\n測試 parse_rates_from_text:")
    test_text = """
    定期存款利率
    1個月: 2.1%
    3個月: 2.3%
    6個月: 2.5%
    12個月: 2.4%
    最低存款10,000港元
    """
    
    rates = parse_rates_from_text("測試銀行", "hkd", test_text)
    print(f"  解析結果: {rates}")
    
    print("\n測試 BANK_URLS:")
    print(f"  共有 {len(BANK_URLS)} 間銀行")
    for bank in list(BANK_URLS.keys())[:3]:
        print(f"  {bank}: HKD={BANK_URLS[bank].get('hkd', 'N/A')}")

def test_data_structure():
    """測試數據結構"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    rates_file = os.path.join(data_dir, 'rates.json')
    
    if os.path.exists(rates_file):
        with open(rates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n當前 rates.json 信息:")
        print(f"  最後更新: {data.get('last_updated', 'N/A')}")
        print(f"  數據源: {data.get('source', 'N/A')}")
        print(f"  銀行數量: {len(data.get('banks', []))}")
        
        # 顯示前3間銀行的結構
        for i, bank in enumerate(data.get('banks', [])[:3]):
            print(f"\n  銀行 {i+1}: {bank['name']}")
            print(f"    類型: {bank.get('type', 'N/A')}")
            print(f"    HKD 利率:")
            for period in ['1m', '3m', '6m', '12m']:
                rate_info = bank['hkd'][period]
                if rate_info.get('rate'):
                    print(f"      {period}: {rate_info['rate']}% (來源: {rate_info.get('source', 'N/A')})")

if __name__ == '__main__':
    print("=" * 50)
    print("香港定期存款利率更新腳本測試")
    print("=" * 50)
    
    test_functions()
    test_data_structure()
    
    print("\n" + "=" * 50)
    print("測試完成")
    print("=" * 50)