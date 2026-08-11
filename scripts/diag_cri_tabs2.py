#!/usr/bin/env python3
"""診斷中原 CRI 頁面 v2：修正 JS，逐個 tab 撳 + 攞數據"""
import json
from collections import Counter
from playwright.sync_api import sync_playwright

RENT_EXTRACT_JS = """
(() => {
  const nuxt = document.querySelector('#__nuxt') && document.querySelector('#__nuxt').__vue__;
  if (!nuxt) return JSON.stringify({error: 'no nuxt'});
  function findTableData(c, depth=0) {
    if (depth > 15) return null;
    if (c.tableData && Array.isArray(c.tableData) && c.tableData.length > 0) return c.tableData;
    if (c.$children) { for (const child of c.$children) { const r = findTableData(child, depth+1); if (r) return r; } }
    return null;
  }
  try {
    const data = findTableData(nuxt);
    if (!data) return JSON.stringify({error: 'no tableData'});
    return JSON.stringify(data.map(e => ({name: e.name, district: e.district, rent: e.index, yield: e.yield})));
  } catch(e) { return JSON.stringify({error: String(e)}); }
})()
"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    page = ctx.new_page()
    page.goto('https://hk.centanet.com/CCI/CRI', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(5000)

    for i, tab_id in enumerate(['tab-HK', 'tab-KL', 'tab-NE', 'tab-NW']):
        try:
            el = page.query_selector(f'#{tab_id}')
            if not el:
                print(f"{tab_id}: 唔存在，skip"); continue
            if i > 0:
                el.click(); page.wait_for_timeout(3500)
            data = page.evaluate(RENT_EXTRACT_JS)
            d = json.loads(data)
            if isinstance(d, dict) and d.get('error'):
                print(f"{tab_id}: error={d['error']}")
            else:
                dc = Counter(e.get('district') for e in d)
                print(f"{tab_id}: {len(d)} 個屋苑, district分佈={dict(dc)}")
                print(f"   sample: {[e['name'] for e in d[:5]]}")
        except Exception as e:
            print(f"{tab_id}: 失敗 - {e}")
    b.close()
