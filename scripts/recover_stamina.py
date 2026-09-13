#!/usr/bin/env python3
"""每 10 分鐘為所有玩家恢復 +10 體力（上限 100）"""
import json, urllib.request, urllib.parse, os

URL = "https://swsdzpakaywkxxngatiw.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN3c2R6cGFrYXl3a3h4bmdhdGl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODY4NTU1NywiZXhwIjoyMTA0MjYxNTU3fQ.XgRJ0dLgFxwPcdnGzvFpzjDbUl1ocRMGPo7cLLZ74XM")
headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

req = urllib.request.Request(f"{URL}/rest/v1/players?select=name,save", headers=headers)
resp = urllib.request.urlopen(req)
players = json.loads(resp.read())

updated = 0
for p in players:
    name = p["name"]
    save = p["save"]
    if isinstance(save, str):
        save = json.loads(save)
    cur = save.get("stamina", 100)
    if cur >= 100:
        continue
    new_stamina = min(100, cur + 10)
    save["stamina"] = new_stamina
    data = json.dumps({"save": save}).encode()
    req2 = urllib.request.Request(
        f"{URL}/rest/v1/players?name=eq.{urllib.parse.quote(name)}",
        data=data, headers={**headers, "Prefer": "return=minimal"},
        method="PATCH"
    )
    try:
        urllib.request.urlopen(req2)
        updated += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")

print(f"✅ 體力恢復完成：{updated} 個玩家已更新")
