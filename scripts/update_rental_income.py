#!/usr/bin/env python3
"""
更新租金收入數據 - 從中原網站攞取
用法:
  python3 update_rental_income.py --price   # 只更新呎價
  python3 update_rental_income.py --rent    # 更新呎租（同時更新呎價）
  python3 update_rental_income.py --all     # 全部更新
"""
import subprocess, json, sys, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / 'data'
JSON_PATH = DATA_DIR / 'rental_income.json'
LOG_PATH = DATA_DIR / 'rental_income_update.log'

HKST = timezone(timedelta(hours=8))
DISTRICT_MAP = {'HK': '香港', 'KL': '九龍', 'KLN': '九龍', 'NTE': '新界', 'NTW': '新界', 'NW': '新界', 'NE': '新界'}
DISTRICT_CODE_MAP = {'HK': 'hk', 'KL': 'kl', 'KLN': 'kl', 'NTE': 'nt', 'NTW': 'nt', 'NW': 'nt', 'NE': 'nt'}

def log(msg):
    ts = datetime.now(HKST).strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def ab(cmd, timeout=30):
    """Run agent-browser command"""
    result = subprocess.run(
        f'agent-browser {cmd}',
        shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"agent-browser failed: {cmd}\n{result.stderr}")
    return result.stdout

def ab_eval(js, timeout=15):
    """Run JS eval via agent-browser, parse JSON result"""
    # Escape single quotes in JS
    js_safe = js.replace("'", "'\\''")
    result = subprocess.run(
        f"agent-browser eval '{js_safe}'",
        shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"eval failed: {result.stderr}")
    raw = result.stdout.strip()
    # The output is a JSON string wrapped in quotes
    try:
        return json.loads(json.loads(raw) if raw.startswith('"') else raw)
    except json.JSONDecodeError:
        # Try direct parse
        return json.loads(raw)

FIND_TABLE_JS = """
const nuxt = document.querySelector("#__nuxt").__vue__;
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
JSON.stringify(findTableData(nuxt));
"""

PRICE_EXTRACT_JS = """
const nuxt = document.querySelector("#__nuxt").__vue__;
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
JSON.stringify(findTableData(nuxt).map(e => ({name: e.name, price: e.index, district: e.district})));
"""

RENT_EXTRACT_JS = """
const nuxt = document.querySelector("#__nuxt").__vue__;
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
JSON.stringify(findTableData(nuxt).map(e => ({name: e.name, rent: e.index, district: e.district, yield: e.yield})));
"""

def scrape_prices():
    """Scrape CCI estate prices from all 4 districts"""
    log("開始攞呎價數據...")
    try:
        ab("open 'https://hk.centanet.com/CCI/index' --timeout 30000")
        ab("wait 3000")
    except Exception as e:
        log(f"開頁失敗: {e}")
        return {}

    all_prices = {}
    tabs = None

    for attempt in range(3):
        try:
            out = ab("snapshot -i -c -s '.el-tabs'", timeout=10)
            tabs = re.findall(r'tab\s+"[^"]*"\s+\[ref=(\w+)\]', out)
            if len(tabs) >= 4:
                break
        except:
            pass
        ab("wait 2000")

    if not tabs or len(tabs) < 4:
        log(f"搵唔到分區 tabs，嘗試用預設 refs")
        tabs = ['e1', 'e2', 'e3', 'e4']

    for i, ref in enumerate(tabs):
        district_names = ['港島', '九龍', '新界東', '新界西']
        try:
            if i > 0:
                ab(f"click @{ref}")
                ab("wait 2000")
            data = ab_eval(PRICE_EXTRACT_JS)
            for e in data:
                all_prices[e['name']] = {'price': e['price'], 'district': e['district']}
            log(f"  {district_names[i]}: {len(data)} 個屋苑")
        except Exception as e:
            log(f"  {district_names[i]} 失敗: {e}")

    try:
        ab("close")
    except:
        pass

    log(f"呎價數據合共 {len(all_prices)} 個屋苑")
    return all_prices

def scrape_rents():
    """Scrape CRI rental data from all 4 districts"""
    log("開始攞呎租數據...")
    try:
        ab("open 'https://hk.centanet.com/CCI/CRI' --timeout 30000")
        ab("wait 3000")
    except Exception as e:
        log(f"開頁失敗: {e}")
        return {}

    all_rents = {}
    tabs = None

    for attempt in range(3):
        try:
            out = ab("snapshot -i -c -s '.el-tabs'", timeout=10)
            tabs = re.findall(r'tab\s+"[^"]*"\s+\[ref=(\w+)\]', out)
            if len(tabs) >= 4:
                break
        except:
            pass
        ab("wait 2000")

    if not tabs or len(tabs) < 4:
        tabs = ['e1', 'e2', 'e3', 'e4']

    for i, ref in enumerate(tabs):
        district_names = ['港島', '九龍', '新界東', '新界西']
        try:
            if i > 0:
                ab(f"click @{ref}")
                ab("wait 2000")
            data = ab_eval(RENT_EXTRACT_JS)
            for e in data:
                all_rents[e['name']] = {'rent': e['rent'], 'yield': e.get('yield'), 'district': e['district']}
            log(f"  {district_names[i]}: {len(data)} 個屋苑")
        except Exception as e:
            log(f"  {district_names[i]} 失敗: {e}")

    try:
        ab("close")
    except:
        pass

    log(f"呎租數據合共 {len(all_rents)} 個屋苑")
    return all_rents

def merge_and_save(price_data, rent_data):
    """Merge price and rent data, calculate yields, save to JSON"""
    log("合併數據並計算回報率...")

    # Load completion years data
    completion_years_path = DATA_DIR / 'estate_completion_years.json'
    completion_years = {}
    if completion_years_path.exists():
        with open(completion_years_path, 'r', encoding='utf-8') as f:
            comp_data = json.load(f)
            completion_years = comp_data.get('estates', {})
        log(f"已載入 {len(completion_years)} 個屋苑嘅入伙年份數據")

    # Calculate current year for building age
    current_year = datetime.now().year

    results = []
    for name, pdata in price_data.items():
        if name not in rent_data:
            continue
        rdata = rent_data[name]
        price_sqft = round(pdata['price'])
        rent_sqft = rdata['rent']
        rental_yield = rdata.get('yield')

        if rental_yield is None and price_sqft > 0:
            rental_yield = round((rent_sqft * 12 / price_sqft) * 100, 2)

        dist_key = pdata['district']
        district_zh = DISTRICT_MAP.get(dist_key, dist_key)
        district_code = DISTRICT_CODE_MAP.get(dist_key, '')

        # Get completion year and calculate building age
        completion_year = completion_years.get(name)
        building_age = None
        if completion_year and completion_year > 0:
            building_age = current_year - completion_year

        results.append({
            'name': name,
            'name_en': name,
            'district': district_zh,
            'district_code': district_code,
            'avg_price_sqft': price_sqft,
            'avg_rent_sqft': rent_sqft,
            'yield': round(rental_yield, 2) if rental_yield else None,
            'building_age': building_age
        })

    results.sort(key=lambda x: x.get('yield') or 0, reverse=True)

    now = datetime.now(HKST)
    output = {
        'last_updated': now.isoformat(),
        'source': '中原數據',
        'price_update_note': f'實用呎價：{now.strftime("%Y-%m-%d")} 更新（中原城市領先指數 CCL）',
        'rent_update_note': '實用呎租：中原城市租金指數 CRI 最新數據',
        'disclaimer': '租金回報率 = 每呎租金 × 12 / 呎價 × 100%。數據僅供參考，不構成投資建議。',
        'estates': results
    }

    # Backup existing file
    if JSON_PATH.exists():
        bak = JSON_PATH.with_suffix('.json.bak')
        import shutil
        shutil.copy2(JSON_PATH, bak)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"已更新 {len(results)} 個屋苑數據")
    if results:
        top = results[0]
        log(f"  最高回報: {top['name']} {top['yield']}%")
        bot = results[-1]
        log(f"  最低回報: {bot['name']} {bot['yield']}%")

def main():
    args = sys.argv[1:]
    if not args:
        args = ['--all']

    update_price = '--price' in args or '--all' in args or '--rent' in args
    update_rent = '--rent' in args or '--all' in args

    log("=" * 50)
    log(f"開始更新租金收入數據 (mode: {'all' if '--all' in args else args})")

    price_data = {}
    rent_data = {}

    if update_price:
        price_data = scrape_prices()
        if not price_data:
            log("呎價數據為空，中止")
            return

    if update_rent:
        rent_data = scrape_rents()
        if not rent_data:
            log("呎租數據為空，中止")
            return

    # If only updating price, keep existing rent data
    if not rent_data and JSON_PATH.exists():
        with open(JSON_PATH, encoding='utf-8') as f:
            existing = json.load(f)
        for e in existing.get('estates', []):
            rent_data[e['name']] = {
                'rent': e['avg_rent_sqft'],
                'yield': e.get('yield'),
                'district': ''
            }

    # If only updating rent, keep existing price data
    if not price_data and JSON_PATH.exists():
        with open(JSON_PATH, encoding='utf-8') as f:
            existing = json.load(f)
        for e in existing.get('estates', []):
            price_data[e['name']] = {
                'price': e['avg_price_sqft'],
                'district': ''
            }

    if price_data and rent_data:
        merge_and_save(price_data, rent_data)
    else:
        log("缺少數據，無法更新")

    log("完成")

if __name__ == '__main__':
    main()
