#!/usr/bin/env python3
"""診斷中原 CRI 頁面：check tab-NE / tab-NW 存在 + 撳完有冇數據"""
import json
from playwright.sync_api import sync_playwright

RENT_EXTRACT_JS = """
const nuxt = document.querySelector("#__nuxt") && document.querySelector("#__nuxt").__vue__;
if (!nuxt) return JSON.stringify({error: 'no nuxt'});
function findTableData(c, depth=0) {
  if (depth > 15) return null;
  if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
  if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
  return null;
}
try {
  const data = findTableData(nuxt);
  return JSON.stringify(data ? data.map(e => ({name: e.name, district: e.district})) : {error: 'no tableData'});
} catch(e) { return JSON.stringify({error: String(e)}); }
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    page = context.new_page()
    page.goto('https://hk.centanet.com/CCI/CRI', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(5000)

    # 1) 列出頁面所有 tab 相關元素
    tabs = page.query_selector_all('[id*="tab"], [class*="tab"]')
    print("=== 頁面 tab 元素 ===")
    for t in tabs[:30]:
        tid = t.get_attribute('id')
        tcls = t.get_attribute('class')
        ttext = (t.inner_text() or '').strip()[:20]
        print(f"  id={tid!r} class={tcls!r} text={ttext!r}")
    print(f"  （tab 元素總數: {len(tabs)}）")

    # 2) 直接 check 4 個 tab-id 存唔存在
    print("\n=== 檢查 tab id 存在性 ===")
    for tid in ['tab-HK', 'tab-KL', 'tab-NE', 'tab-NW']:
        el = page.query_selector(f'#{tid}')
        print(f"  #{tid}: {'✓ 存在' if el else '✗ 不存在'}")

    # 3) 逐個撳 + 攞數據量（用返 RENT_EXTRACT_JS）
    print("\n=== 逐個 tab 撳 + 攞數據 ===")
    for i, tab_id in enumerate(['tab-HK', 'tab-KL', 'tab-NE', 'tab-NW']):
        try:
            el = page.query_selector(f'#{tab_id}')
            if not el:
                print(f"  {tab_id}: 唔存在，skip")
                continue
            if i > 0:
                el.click()
                page.wait_for_timeout(3500)
            data = page.evaluate(RENT_EXTRACT_JS)
            d = json.loads(data) if isinstance(data, str) else data
            if isinstance(d, dict) and d.get('error'):
                print(f"  {tab_id}: error={d['error']}")
            else:
                names = [e['name'] for e in d]
                # district 分佈
                from collections import Counter
                dc = Counter(e.get('district') for e in d)
                print(f"  {tab_id}: {len(d)} 個屋苑, district={dict(dc)}")
                print(f"         sample: {names[:6]}")
        except Exception as e:
            print(f"  {tab_id}: 撳/攞失敗 - {e}")

    browser.close()
