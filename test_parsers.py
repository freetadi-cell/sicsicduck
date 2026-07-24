#!/usr/bin/env python3
"""測試修復後嘅 parser"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from parsers.shacom import parse as parse_shacom
from parsers.fubon import parse as parse_fubon
from parsers.livi import parse as parse_livi
from parsers.airstar import parse as parse_airstar
from parsers.za import parse as parse_za
from parsers.welab import parse as parse_welab
from parsers.chiyu import parse as parse_chiyu

# Test data from web_fetch
shacom_text = """### 新資金定期存款年利率優惠
 1 個月  3 個月  6 個月  12 個月
 美元 3.30% 3.65% 3.70% 3.70%
 人民幣 0.75% 1.25% 1.30% 1.30%

### 個人網上銀行 / 流動銀行定期存款年利率優惠
 1 個月  3 個月  6 個月  12 個月
 港元 2.13% 2.78% 2.93% 2.98%
 美元 2.98% 3.48% 3.53% 3.53%
 人民幣 0.58% 0.98% 1.03% 1.03%"""

fubon_text = """### 新資金定期存款優惠
存款期 三個月 六個月 九個月 十二個月
港元 2.95% 3.1% 3.1% 3.1%
美元 4.1% / / /

### Fubon+ 手機應用程式限定 ─ 特優港元定期存款優惠
存款期/存款金額 一個月 兩個月 三個月 四個月 六個月 十二個月
港元500,000 或以上 2.45% 2.55% 2.9% 2.9% 3.05% 3.05%"""

livi_text = """## 存款期及年利率 (HKD)
存入金額（HKD） 500 - 5萬以下 5萬+
7 日 0.25% 0.25%
1 個月 0.50% 1.20%
3 個月 1.10% 2.80%
6 個月 1.30% 2.60%
12 個月 1.60% 2.70%

## 存款期及年利率 (USD)
1個月 1.50%
3個月 3.90%
6個月 3.40%
12個月 3.30%"""

print("=" * 60)
print("測試上海商業銀行 (shacom)")
print("=" * 60)
result = parse_shacom(shacom_text)
if result:
    print("✅ 成功")
    for currency in ['hkd', 'usd', 'cny']:
        if currency in result:
            print(f"  {currency.upper()}: {list(result[currency].keys())}")
            for period, data in list(result[currency].items())[:2]:
                print(f"    {period}: {data['rate']}%")
else:
    print("❌ 失敗")

print()
print("=" * 60)
print("測試富邦銀行 (fubon)")
print("=" * 60)
result = parse_fubon(fubon_text)
if result:
    print("✅ 成功")
    for currency in ['hkd', 'usd']:
        if currency in result:
            print(f"  {currency.upper()}: {list(result[currency].keys())}")
            for period, data in list(result[currency].items())[:2]:
                print(f"    {period}: {data['rate']}%")
else:
    print("❌ 失敗")

print()
print("=" * 60)
print("測試理慧銀行 (livi)")
print("=" * 60)
result = parse_livi(livi_text)
if result:
    print("✅ 成功")
    for currency in ['hkd', 'usd']:
        if currency in result:
            print(f"  {currency.upper()}: {list(result[currency].keys())}")
            for period, data in list(result[currency].items())[:2]:
                print(f"    {period}: {data['rate']}%")
else:
    print("❌ 失敗")

print()
print("=" * 60)
print("所有測試完成")
print("=" * 60)
