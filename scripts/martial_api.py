#!/usr/bin/env python3
"""
Wulin martial arts API helper — skill queries via Supabase REST.
Used by wulin.html frontend via inline fetch calls.
"""
import urllib.request
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN3c2R6cGFrYXl3a3h4bmdhdGl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODY4NTU1NywiZXhwIjoyMTA0MjYxNTU3fQ.XgRJ0dLgFxwPcdnGzvFpzjDbUl1ocRMGPo7cLLZ74XM"
BASE = "https://swsdzpakaywkxxngatiw.supabase.co"

def _get(table, query=""):
    from urllib.parse import quote
    url = f"{BASE}/rest/v1/{table}?{quote(query, safe='=&?')}"
    req = urllib.request.Request(url, headers={
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}"
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode())

def _post(table, data):
    url = f"{BASE}/rest/v1/{table}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }, method="POST")
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode())

def _delete(table, query):
    url = f"{BASE}/rest/v1/{table}?{query}"
    req = urllib.request.Request(url, headers={
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }, method="DELETE")
    resp = urllib.request.urlopen(req, timeout=15)

# === Skills database ===
def get_all_skills():
    return _get("skills", "select=key,name,type,power,rarity,description&order=type,power.desc")

def get_npc_skills(npc_key):
    return _get("npc_skills", f"select=skill_key,proficiency&npc_key=eq.{npc_key}")

def get_player_skills(player_name):
    return _get("player_skills", f"select=skill_key,equipped&player_name=eq.{player_name}")

def learn_skill(player_name, skill_key, equipped=False):
    try:
        return _post("player_skills", {
            "player_name": player_name,
            "skill_key": skill_key,
            "equipped": equipped
        })
    except Exception as e:
        if "duplicate" in str(e).lower():
            return None  # already learned
        raise

def equip_skill(player_name, skill_key, slot_type):
    """Equip a skill in its slot (martial/neigong/qinggong).
    Unequip current skill in that slot first."""
    # Get skill type
    skills = _get("skills", f"select=type&key=eq.{skill_key}")
    if not skills:
        return None
    skill_type = skills[0]["type"]

    # Unequip current skill in same slot
    current = _get("player_skills",
        f"select=skill_key&player_name=eq.{player_name}&equipped=eq.true")
    for s in current:
        s_info = _get("skills", f"select=type&key=eq.{s['skill_key']}")
        if s_info and s_info[0]["type"] == skill_type:
            _delete("player_skills",
                f"player_name=eq.{player_name}&skill_key=eq.{s['skill_key']}")
            # Re-insert without equipped
            _post("player_skills", {
                "player_name": player_name,
                "skill_key": s["skill_key"],
                "equipped": False
            })

    # Ensure learned, then equip
    learn_skill(player_name, skill_key, True)

# === Rarity check ===
RARITY_TIER = {"common": 1, "uncommon": 2, "rare": 3, "legendary": 4}
MAX_SPAR_TIER = 2  # common + uncommon only

def can_learn_via_spar(skill_key):
    """切磋只可以學中階以下（common/uncommon）"""
    skills = _get("skills", f"select=rarity&key=eq.{skill_key}")
    if not skills:
        return False
    return RARITY_TIER.get(skills[0]["rarity"], 0) <= MAX_SPAR_TIER

# === Test ===
if __name__ == "__main__":
    print("=== All Skills ===")
    for s in get_all_skills():
        print(f"  [{s['type']}] {s['name']} (power={s['power']}, rarity={s['rarity']})")

    print("\n=== NPC Skills ===")
    for npc in ["guojing", "yangguo", "xiaolongnu"]:
        skills = get_npc_skills(npc)
        names = [s["skill_key"] for s in skills]
        print(f"  {npc}: {names}")

    print("\n=== Rarity Check ===")
    print(f"  降龍十八掌 spar: {can_learn_via_spar('降龍十八掌')}")
    print(f"  基礎步法 spar: {can_learn_via_spar('基礎步法')}")
    print(f"  鐵掌功 spar: {can_learn_via_spar('鐵掌功')}")
