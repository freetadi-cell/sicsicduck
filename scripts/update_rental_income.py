#!/usr/bin/env python3
"""
更新租金收入數據 - 從中原網站攞取（用 Playwright）
用法:
  python3 update_rental_income.py --price   # 只更新呎價
  python3 update_rental_income.py --rent    # 更新呎租（同時更新呎價）
  python3 update_rental_income.py --all     # 全部更新
"""
import json, sys, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / 'data'
JSON_PATH = DATA_DIR / 'rental_income.json'
LOG_PATH = DATA_DIR / 'rental_income_update.log'

HKST = timezone(timedelta(hours=8))
DISTRICT_MAP = {'HK': '香港', 'KL': '九龍', 'KLN': '九龍', 'NTE': '新界', 'NTW': '新界', 'NW': '新界', 'NE': '新界'}
DISTRICT_CODE_MAP = {'HK': 'hk', 'KL': 'kl', 'KLN': 'kl', 'NTE': 'nt', 'NTW': 'nt', 'NW': 'nt', 'NE': 'nt'}

# 每個 tab 應該含嘅代表屋苑（用嚟驗證切換成功，唔會撳完仲係上一個 tab 嘅數據）
# 以 2026-06 實測網頁嘅真實名單為準
DISTRICT_SAMPLE_ESTATES = {
    'HK': ['太古城', '海怡半島', '杏花邨', '康怡花園', '置富花園'],      # 港島
    'KL': ['美孚新邨', '黃埔花園', '麗港城', '新都城', '維景灣畔'],      # 九龍
    'NE': ['沙田第一城', '新港城', '名城', '迎海', '大埔中心', '太湖花園'],  # 新界東
    'NW': ['嘉湖山莊', '珀麗灣', '海濱花園', '麗城花園', '映灣園', '荃威花園'],  # 新界西
}

# CRI 每個 tab 應該有一個識別標記：用「唔屬於該區嘅屋苑」嚟檢測重複/冇切換
# 例如新界東唔應該出現太古城（港島代表）
DISTRICT_ALIEN_SAMPLES = {
    'HK': ['沙田第一城', '嘉湖山莊'],   # 港島 tab 唔應該有新界屋苑
    'KL': ['沙田第一城', '嘉湖山莊'],   # 九龍 tab 唔應該有新界屋苑
    'NE': ['太古城', '海怡半島', '美孚新邨'],  # 新界東唔應該有港島/九龍代表
    'NW': ['太古城', '海怡半島', '美孚新邨'],  # 新界西唔應該有港島/九龍代表
}


def _verify_tab_switch(names, tab_id):
    """驗證攞到嘅屋苑名單係咪真係屬於目標區域。
    回傳 True = 切換成功；False = 攞到重複/港島/九龍數據（切換失敗）。"""
    if not names:
        return False
    # tab_id 係 'tab-NE' 格式，剝走 'tab-' 前綴先對返 DISTRICT_SAMPLE_ESTATES 嘅 key
    region_key = tab_id.replace('tab-', '') if tab_id.startswith('tab-') else tab_id
    sample = DISTRICT_SAMPLE_ESTATES.get(region_key, [])
    if not sample:
        return True  # 冇 sample 定義就唔阻撓（保守通過）
    # 目標區嘅代表屋苑：至少中一個先當切換成功（攞到該區嘢）
    return any(n in names for n in sample)


def log(msg):
    ts = datetime.now(HKST).strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

PRICE_EXTRACT_JS = """
const nuxt = document.querySelector("#__nuxt").__vue__;
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
const data = findTableData(nuxt);
JSON.stringify(data.map(e => ({name: e.name, price: e.index, district: e.district})));
"""

RENT_EXTRACT_JS = """
const nuxt = document.querySelector("#__nuxt").__vue__;
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
const data = findTableData(nuxt);
JSON.stringify(data.map(e => ({name: e.name, rent: e.index, district: e.district, yield: e.yield})));
"""

def scrape_prices():
    """Scrape CCI estate prices from all 4 districts using Playwright"""
    log("開始攞呎價數據...")
    all_prices = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        try:
            log("  開啟中原 CCI 頁面...")
            page.goto('https://hk.centanet.com/CCI/index', timeout=30000, wait_until='networkidle')
            page.wait_for_timeout(5000)
            
            # Find district tabs (correct selectors from inspection)
            tabs = ['tab-HK', 'tab-KL', 'tab-NE', 'tab-NW']
            district_names = ['港島', '九龍', '新界東', '新界西']
            
            for i, tab_id in enumerate(tabs):
                district_zh = district_names[i]
                for attempt in range(3):  # 最多重試 3 次
                    try:
                        if i > 0:
                            # Click on the tab
                            page.click(f'#{tab_id}')
                            page.wait_for_timeout(4000)

                        # Extract data using JavaScript
                        data = page.evaluate(PRICE_EXTRACT_JS)

                        # Parse JSON string if needed
                        if isinstance(data, str):
                            import json
                            data = json.loads(data)

                        names = [e.get('name', '') for e in data]

                        # 驗證切換成功：攞到嘅必須包含目標區代表屋苑
                        if i > 0 and not _verify_tab_switch(names, tab_id):
                            log(f"  {district_zh} 切換驗證失敗(第{attempt+1}次)，攞到 {len(data)} 個但唔似 {district_zh}，重試...")
                            page.wait_for_timeout(2500 * (attempt + 1))
                            continue

                        for e in data:
                            n = e.get('name')
                            if not n:
                                continue
                            all_prices[n] = {'price': e.get('price'), 'district': e.get('district')}

                        log(f"  {district_zh}: {len(data)} 個屋苑")
                        break  # 成功，唔使重試
                    except Exception as e:
                        log(f"  {district_zh} 第{attempt+1}次失敗: {e}")
                        if attempt < 2:
                            page.wait_for_timeout(3000)
                            continue

        except Exception as e:
            log(f"開頁失敗: {e}")
        
        finally:
            browser.close()
    
    log(f"呎價數據合共 {len(all_prices)} 個屋苑")
    return all_prices

def scrape_rents():
    """Scrape CRI rental data from all 4 districts using Playwright"""
    log("開始攞呎租數據...")
    all_rents = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        try:
            log("  開啟中原 CRI 頁面...")
            page.goto('https://hk.centanet.com/CCI/CRI', timeout=30000, wait_until='networkidle')
            page.wait_for_timeout(5000)
            
            # Find district tabs (correct selectors from inspection)
            tabs = ['tab-HK', 'tab-KL', 'tab-NE', 'tab-NW']
            district_names = ['港島', '九龍', '新界東', '新界西']
            
            for i, tab_id in enumerate(tabs):
                district_zh = district_names[i]
                for attempt in range(3):  # 最多重試 3 次
                    try:
                        if i > 0:
                            # Click on the tab
                            page.click(f'#{tab_id}')
                            page.wait_for_timeout(4000)

                        # Extract data using JavaScript
                        data = page.evaluate(RENT_EXTRACT_JS)

                        # Parse JSON string if needed
                        if isinstance(data, str):
                            import json
                            data = json.loads(data)

                        names = [e.get('name', '') for e in data]

                        # 驗證切換成功：攞到嘅必須包含目標區代表屋苑
                        if i > 0 and not _verify_tab_switch(names, tab_id):
                            log(f"  {district_zh} 切換驗證失敗(第{attempt+1}次)，攞到 {len(data)} 個但唔似 {district_zh}，重試...")
                            page.wait_for_timeout(2500 * (attempt + 1))
                            continue

                        for e in data:
                            n = e.get('name')
                            if not n:
                                continue
                            all_rents[n] = {'rent': e.get('rent'), 'yield': e.get('yield'), 'district': e.get('district')}

                        log(f"  {district_zh}: {len(data)} 個屋苑")
                        break  # 成功，唔使重試
                    except Exception as e:
                        log(f"  {district_zh} 第{attempt+1}次失敗: {e}")
                        if attempt < 2:
                            page.wait_for_timeout(3000)
                            continue

        except Exception as e:
            log(f"開頁失敗: {e}")
        
        finally:
            browser.close()
    
    log(f"呎租數據合共 {len(all_rents)} 個屋苑")
    return all_rents

def merge_and_save(price_data, rent_data):
    """Merge price and rent data, calculate yields, save to JSON"""
    log("合併數據並計算回報率...")

    # Load existing data (for fallback: 呎租一時攞唔到就保留舊值)
    old_by_name = {}
    if JSON_PATH.exists():
        try:
            old = json.loads(JSON_PATH.read_text(encoding='utf-8'))
            for e in old.get('estates', []):
                old_by_name[e.get('name')] = e
        except Exception:
            pass

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
    skipped = []
    fallback_used = 0
    for name, pdata in price_data.items():
        rdata = rent_data.get(name)
        dist_key = pdata['district']
        district_zh = DISTRICT_MAP.get(dist_key, dist_key)
        district_code = DISTRICT_CODE_MAP.get(dist_key, '')

        # 搵唔到今次呎租 → 用返舊 json 數據頂住，唔好直接洗走（防止新界全軍覆沒）
        use_old_fallback = False
        if rdata is None:
            old_e = old_by_name.get(name)
            if old_e and old_e.get('avg_rent_sqft'):
                rdata = {'rent': old_e['avg_rent_sqft'], 'yield': old_e.get('yield')}
                use_old_fallback = True
                fallback_used += 1
            else:
                skipped.append(name)
                continue

        price_sqft = round(pdata['price'])
        rent_sqft = rdata['rent']
        rental_yield = rdata.get('yield')

        if rental_yield is None and price_sqft > 0:
            rental_yield = round((rent_sqft * 12 / price_sqft) * 100, 2)

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