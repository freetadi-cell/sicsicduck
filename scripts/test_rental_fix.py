#!/usr/bin/env python3
"""單元測試：驗證 update_rental_income.py 切換驗證 + 兜底邏輯"""
import sys, os, json, importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("uri", ROOT / "scripts" / "update_rental_income.py")
uri = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uri)

ok = 0
fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fail += 1
        print(f"  ❌ {name} {detail}")

print("=== 1. _verify_tab_switch 切換驗證 ===")
# 新界東 tab 攞到真新界東數據 → 應該 pass
check("NE tab 攞到沙田第一城 → True",
      uri._verify_tab_switch(['沙田第一城', '新港城', '名城'], 'tab-NE'))
# 新界東 tab 攞到港島數據（重複 bug）→ 應該 fail
check("NE tab 攞到太古城（重複港島）→ False",
      not uri._verify_tab_switch(['太古城', '海怡半島', '杏花邨'], 'tab-NE'))
# 新界西 tab 攞到真新界西 → True
check("NW tab 攞到嘉湖山莊 → True",
      uri._verify_tab_switch(['嘉湖山莊', '珀麗灣', '映灣園'], 'tab-NW'))
# 新界西 tab 攞到九龍數據 → False
check("NW tab 攞到美孚新邨（重複九龍）→ False",
      not uri._verify_tab_switch(['美孚新邨', '黃埔花園'], 'tab-NW'))
# 港島 tab（i=0 唔會驗證，但個 helper 直接測：真港島數據要過）
check("HK 攞到太古城 → True",
      uri._verify_tab_switch(['太古城', '海怡半島'], 'tab-HK'))
# 空數據 → False
check("空數據 → False", not uri._verify_tab_switch([], 'tab-NE'))

print("=== 2. merge_and_save 兜底邏輯 ===")
# 構造假 price_data（有齊143個，含新界）+ 只提供港島/九龍 rent_data
price_data = {}
rent_data = {}
for i in range(40):
    price_data[f'港苑{i}'] = {'price': 10000, 'district': 'HK'}
    price_data[f'九苑{i}'] = {'price': 10000, 'district': 'KL'}
for i in range(30):
    price_data[f'新東{i}'] = {'price': 10000, 'district': 'NE'}
for i in range(33):
    price_data[f'新西{i}'] = {'price': 10000, 'district': 'NW'}
# rent_data 只有港島+九龍（模擬新界 tab 抓取失敗）
for i in range(40):
    rent_data[f'港苑{i}'] = {'rent': 45, 'yield': None}
    rent_data[f'九苑{i}'] = {'rent': 45, 'yield': None}

# 模擬舊 json 有新界數據（要兜底嘅來源）
old_estates = []
for i in range(30):
    old_estates.append({'name': f'新東{i}', 'avg_rent_sqft': 40, 'yield': 4.8})
for i in range(33):
    old_estates.append({'name': f'新西{i}', 'avg_rent_sqft': 38, 'yield': 4.5})

# 臨時寫舊 json，再 call merge_and_save
old_json = ROOT / 'data' / 'rental_income.json'
bak = old_json.read_bytes()
try:
    old_json.write_text(json.dumps({'estates': old_estates}, ensure_ascii=False), encoding='utf-8')
    uri.merge_and_save(price_data, rent_data)
    merged = json.loads(old_json.read_text(encoding='utf-8'))
    names = [e['name'] for e in merged['estates']]
    # 應該有齊所有 143 個（新界靠兜底補返）
    check("總數 = 143（港40+九40+新東30+新西33）", len(names) == 143, f"實際 {len(names)}")
    check("新東兜底補返（30個）", sum(1 for n in names if n.startswith('新東')) == 30)
    check("新西兜底補返（33個）", sum(1 for n in names if n.startswith('新西')) == 33)
    check("兜底後新界有樓呎租（40）", all(e['avg_rent_sqft'] == 40 for e in merged['estates'] if e['name'].startswith('新東')))
    # 有兜底老新界數據度保留 building_age / district
    ne = [e for e in merged['estates'] if e['name'].startswith('新東')][0]
    check("新界 district 正確（新界）", ne['district'] == '新界', ne['district'])
finally:
    old_json.write_bytes(bak)

print(f"\n結果: {ok} pass, {fail} fail")
sys.exit(1 if fail else 0)
