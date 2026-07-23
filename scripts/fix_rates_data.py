#!/usr/bin/env python3
"""
修復 rates.json 數據質量問題：

1. 利率單位錯誤：大部分銀行利率存為百分比（240.00），需轉為小數（0.024）
2. 數據結構不一致：部分銀行缺少 key 字段
3. 重複數據：同一銀行出現多次
4. 異常值：exchange rate 被當成定存利率

修復策略：
- 檢測並修正利率單位（如果 rate > 1.0，除以 100）
- 移除 exchange 類型嘅利率（exchange rate 唔係定存）
- 合併重複銀行數據
- 清理異常值（rate > 0.10 或 rate < 0.001）
"""

import json
import os
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATES_FILE = os.path.join(BASE_DIR, 'data', 'rates.json')

HK_TZ = timezone(timedelta(hours=8))


def fix_rate(rate):
    """修正利率單位
    
    如果 rate > 1.0，應該係百分比，需要除以 100
    如果 0.001 <= rate <= 0.10，已經係小數，唔使改
    """
    if rate is None:
        return None
    
    # 如果大於 1，應該係百分比
    if rate > 1.0:
        return rate / 100
    
    # 如果係合理嘅小數範圍（0.1% - 10%）
    if 0.001 <= rate <= 0.10:
        return rate
    
    # 其他情況（異常值）
    return None


def fix_period_data(pd):
    """修正一個 period 嘅數據"""
    if not isinstance(pd, dict):
        return pd
    
    fixed = {}
    
    # Simple rate structure
    if 'rate' in pd:
        fund_type = pd.get('fund_type', '')
        
        # Skip exchange rates
        if fund_type == 'exchange':
            return None
        
        fixed_rate = fix_rate(pd['rate'])
        if fixed_rate is not None:
            fixed['rate'] = fixed_rate
            fixed['min_deposit'] = pd.get('min_deposit', 0)
            fixed['note'] = pd.get('note', '')
            fixed['source'] = pd.get('source', '')
            fixed['fund_type'] = fund_type if fund_type else 'general'
            fixed['conditions'] = pd.get('conditions', [])
    
    # Nested fund_type structure
    for ftype in ['new_funds', 'new_customer', 'existing_funds', 'general']:
        if ftype in pd:
            fd = pd[ftype]
            if isinstance(fd, dict):
                fixed_rate = fix_rate(fd.get('rate'))
                if fixed_rate is not None:
                    fixed[ftype] = {
                        'rate': fixed_rate,
                        'min_deposit': fd.get('min_deposit', 0),
                        'note': fd.get('note', ''),
                        'source': fd.get('source', ''),
                        'conditions': fd.get('conditions', [])
                    }
    
    return fixed if fixed else None


def fix_rates_json():
    """修復 rates.json"""
    
    # 讀取現有數據
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"修復前：{len(data['banks'])} 間銀行")
    
    # 追蹤已處理嘅銀行（用 name_en 作為 key）
    seen_banks = {}
    
    for bank in data['banks']:
        name = bank['name']
        name_en = bank.get('name_en', '')
        key = bank.get('key', '')
        
        # 用 name_en 或者 name 作為唯一標識
        bank_id = name_en if name_en else name
        
        # 修正 HKD 數據
        hkd = bank.get('hkd', {})
        fixed_hkd = {}
        for period, pd in hkd.items():
            fixed_pd = fix_period_data(pd)
            if fixed_pd:
                fixed_hkd[period] = fixed_pd
        
        # 修正 USD 數據
        usd = bank.get('usd', {})
        fixed_usd = {}
        for period, pd in usd.items():
            fixed_pd = fix_period_data(pd)
            if fixed_pd:
                fixed_usd[period] = fixed_pd
        
        # 修正 CNY 數據
        cny = bank.get('cny', {})
        fixed_cny = {}
        for period, pd in cny.items():
            fixed_pd = fix_period_data(pd)
            if fixed_pd:
                fixed_cny[period] = fixed_pd
        
        # 合併重複銀行
        if bank_id in seen_banks:
            # 合併數據
            existing = seen_banks[bank_id]
            existing['hkd'].update(fixed_hkd)
            existing['usd'].update(fixed_usd)
            existing['cny'].update(fixed_cny)
            if key and not existing.get('key'):
                existing['key'] = key
        else:
            # 新增銀行
            seen_banks[bank_id] = {
                'name': name,
                'name_en': name_en,
                'key': key,
                'type': bank.get('type', 'traditional'),
                'logo_color': bank.get('logo_color', ''),
                'hkd': fixed_hkd,
                'usd': fixed_usd,
                'cny': fixed_cny
            }
    
    # 建立新嘅 banks 列表
    fixed_banks = list(seen_banks.values())
    
    # 更新數據
    data['banks'] = fixed_banks
    data['last_updated'] = datetime.now(HK_TZ).isoformat()
    
    print(f"修復後：{len(fixed_banks)} 間銀行")
    
    # 儲存修復後嘅數據
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已修復 {RATES_FILE}")
    
    # 輸出統計
    total_periods = 0
    total_rates = 0
    
    for bank in fixed_banks:
        for currency in ['hkd', 'usd', 'cny']:
            periods = bank.get(currency, {})
            total_periods += len(periods)
            for pd in periods.values():
                if isinstance(pd, dict):
                    total_rates += 1
    
    print(f"   總共 {total_periods} 個存款期，{total_rates} 個利率")


if __name__ == '__main__':
    fix_rates_json()