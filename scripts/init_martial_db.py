#!/usr/bin/env python3
"""
Initialize Wulin martial arts database on Supabase via Management API (SQL endpoint).
"""
import urllib.request
import json
import time

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN3c2R6cGFrYXl3a3h4bmdhdGl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODY4NTU1NywiZXhwIjoyMTA0MjYxNTU3fQ.XgRJ0dLgFxwPcdnGzvFpzjDbUl1ocRMGPo7cLLZ74XM"
BASE = "https://swsdzpakaywkxxngatiw.supabase.co"

def run_sql(sql_text):
    """Execute SQL via PostgREST /rpc endpoint"""
    payload = json.dumps({"query": sql_text}).encode()
    req = urllib.request.Request(
        f"{BASE}/rest/v1/rpc/exec_sql",
        data=payload,
        headers={
            "apikey": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def insert_skill(key, name, skill_type, power, rarity, desc):
    """Insert a skill using POST"""
    payload = json.dumps({
        "key": key, "name": name, "type": skill_type,
        "power": power, "rarity": rarity, "description": desc
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/rest/v1/skills",
        data=payload,
        headers={
            "apikey": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"  ⚠️ {name}: {e}")
        return False

def insert_npc_skill(npc_key, skill_key):
    """Insert npc_skill using POST"""
    payload = json.dumps({
        "npc_key": npc_key, "skill_key": skill_key, "proficiency": 100
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/rest/v1/npc_skills",
        data=payload,
        headers={
            "apikey": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"  ⚠️ {npc_key}/{skill_key}: {e}")
        return False

# === Step 0: Create exec_sql function via direct SQL ===
print("=== Creating exec_sql helper ===")
sql_create_fn = """
CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS json AS $$
BEGIN
  EXECUTE query;
  RETURN '{"ok":true}'::json;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
"""
result = run_sql(sql_create_fn)
print(f"  Result: {result}")

# Check if tables exist
print("\n=== Checking existing tables ===")
req = urllib.request.Request(
    f"{BASE}/rest/v1/skills?select=id&limit=1",
    headers={
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}"
    }
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print("  skills table exists!")
    TABLES_EXIST = True
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("  skills table NOT found - need to create via SQL Editor")
        TABLES_EXIST = False
    else:
        print(f"  Error: {e}")
        TABLES_EXIST = False

if not TABLES_EXIST:
    print("\n❌ Cannot create tables via API. Need to use SQL Editor.")
    print("Please go to Supabase Dashboard → SQL Editor and run the SQL below:")
    print("=" * 60)
    print("""
CREATE TABLE IF NOT EXISTS skills (
  id SERIAL PRIMARY KEY,
  key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('martial', 'neigong', 'qinggong')),
  power INTEGER NOT NULL DEFAULT 0,
  description TEXT,
  rarity TEXT DEFAULT 'common' CHECK (rarity IN ('common', 'uncommon', 'rare', 'legendary')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_skills (
  id SERIAL PRIMARY KEY,
  player_name TEXT NOT NULL,
  skill_key TEXT NOT NULL REFERENCES skills(key),
  equipped BOOLEAN DEFAULT FALSE,
  learned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(player_name, skill_key)
);

CREATE TABLE IF NOT EXISTS npc_skills (
  id SERIAL PRIMARY KEY,
  npc_key TEXT NOT NULL,
  skill_key TEXT NOT NULL REFERENCES skills(key),
  proficiency INTEGER DEFAULT 100,
  UNIQUE(npc_key, skill_key)
);

CREATE OR REPLACE FUNCTION exec_sql(query text) RETURNS json AS $$
BEGIN
  EXECUTE query;
  RETURN '{"ok":true}'::json;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Enable RLS but allow all for service_role
ALTER TABLE skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE npc_skills ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for service_role" ON skills FOR ALL USING (true);
CREATE POLICY "Allow all for service_role" ON player_skills FOR ALL USING (true);
CREATE POLICY "Allow all for service_role" ON npc_skills FOR ALL USING (true);
""")
    print("=" * 60)
    exit(1)

# === Seed data ===
print("\n=== Seeding skills ===")
SKILLS = [
    # 武功 (martial)
    ("降龍十八掌", "martial", 95, "legendary", "剛猛無匹嘅掌法，天下第一剛勁"),
    ("黯然銷魂掌", "martial", 93, "legendary", "楊過自創，以情入武，悲憤激昂"),
    ("雙手互搏", "martial", 95, "legendary", "一心二用，左右同時施展不同武功"),
    ("九陰白骨爪", "martial", 80, "rare", "九陰真經所載，凌厲無情"),
    ("玉女劍法", "martial", 82, "rare", "古墓派劍法，飄逸靈動"),
    ("打狗棒法", "martial", 85, "rare", "丐幫幫主代代相傳，靈巧多變"),
    ("落英神劍掌", "martial", 78, "rare", "桃花島武功，華美如落英"),
    ("一陽指", "martial", 82, "rare", "大理段氏絕學，指力通神"),
    ("鐵掌功", "martial", 75, "uncommon", "鐵掌幫絕學，掌力剛猛"),
    ("拂塵功", "martial", 73, "uncommon", "古墓派外門兵器功夫"),
    ("全真劍法", "martial", 70, "uncommon", "全真教正宗劍法"),
    ("空明拳", "martial", 88, "legendary", "周伯通所創，以虛御實"),
    ("瑛姑指法", "martial", 50, "common", "基礎指法"),
    ("劈空掌", "martial", 60, "uncommon", "掌風可傷人於數步之外"),
    ("天羅地網掌", "martial", 55, "uncommon", "古墓派入門掌法"),
    ("一劍無鋒", "martial", 65, "uncommon", "重劍無鋒，大巧不工"),
    ("冰魄銀針", "martial", 68, "uncommon", "李莫愁暗器功夫"),
    ("倒亂刃法", "martial", 72, "uncommon", "公孫止陰陽倒亂雙刃"),
    ("落英神劍", "martial", 76, "rare", "桃花島劍法精髓"),
    ("彈指神通", "martial", 80, "rare", "黃藥師絕學，彈射暗器"),

    # 內功 (neigong)
    ("九陰真經", "neigong", 95, "legendary", "天下至高內功心法，蘊含武學至理"),
    ("九陽真經", "neigong", 93, "legendary", "至剛至陽，內力生生不息"),
    ("先天功", "neigong", 88, "legendary", "王重陽所傳，全真教鎮派之寶"),
    ("玉女心經", "neigong", 85, "rare", "古墓派最高內功，需二人合練"),
    ("蛤蟆功", "neigong", 80, "rare", "歐陽鋒絕學，蓄力反擊"),
    ("易筋經", "neigong", 90, "legendary", "少林至高內功，脫胎換骨"),
    ("全真心法", "neigong", 65, "uncommon", "全真教基礎內功"),
    ("古墓內功", "neigong", 68, "uncommon", "古墓派基礎內功"),
    ("紫霞神功", "neigong", 60, "uncommon", "華山派內功"),
    ("混元功", "neigong", 55, "common", "基礎內功，強身健體"),
    ("玄鐵重劍內力", "neigong", 82, "rare", "以重劍鍛鍊出嘅深厚內力"),
    ("藏邊大手印", "neigong", 70, "uncommon", "密宗內功"),
    ("金剛不壞體", "neigong", 85, "rare", "刀槍不入，防禦極強"),
    ("基礎吐納", "neigong", 10, "common", "最基礎嘅呼吸吐納法"),

    # 輕功 (qinggong)
    ("古墓輕功", "qinggong", 95, "legendary", "古墓派天下無雙嘅輕功，如燕似蝶"),
    ("螺旋九影", "qinggong", 88, "legendary", "身形幻化九影，身法至高"),
    ("凌波微步", "qinggong", 90, "legendary", "腳踏七星，步法飄逸無蹤"),
    ("一葦渡江", "qinggong", 82, "rare", "踏水而行，如履平地"),
    ("草上飛", "qinggong", 70, "uncommon", "足尖點草而行，速度極快"),
    ("梯雲縱", "qinggong", 75, "rare", "武當輕功，借力騰空"),
    ("燕子三抄水", "qinggong", 65, "uncommon", "水面三次點水而過"),
    ("壁虎游牆", "qinggong", 60, "uncommon", "攀牆如行平地"),
    ("神行百變", "qinggong", 78, "rare", "身法詭異多變"),
    ("踏雪無痕", "qinggong", 72, "uncommon", "雪地不留足跡"),
    ("雁行功", "qinggong", 50, "common", "基礎輕功，騰躍敏捷"),
    ("陸地飛騰", "qinggong", 55, "common", "奔跑速度倍增"),
    ("蜻蜓點水", "qinggong", 62, "uncommon", "水面輕點而過"),
    ("基礎步法", "qinggong", 10, "common", "最基礎嘅步法訓練"),
]

ok_count = 0
for name, stype, power, rarity, desc in SKILLS:
    if insert_skill(name, name, stype, power, rarity, desc):
        ok_count += 1
        print(f"  ✅ {name} ({stype})")
    else:
        print(f"  ❌ {name}")
print(f"  Skills: {ok_count}/{len(SKILLS)}")

# === Seed NPC skills ===
print("\n=== Seeding NPC skills ===")
NPC_SKILLS = {
    "guojing": ["降龍十八掌", "九陰真經", "空明拳", "基礎步法"],
    "yangguo": ["黯然銷魂掌", "雙手互搏", "玄鐵重劍內力", "古墓輕功"],
    "xiaolongnu": ["玉女劍法", "玉女心經", "古墓內功", "古墓輕功"],
    "zhoubotong": ["雙手互搏", "空明拳", "先天功", "螺旋九影"],
    "liguomochou": ["拂塵功", "冰魄銀針", "古墓內功", "古墓輕功"],
    "huangrong": ["落英神劍掌", "打狗棒法", "彈指神通", "神行百變"],
    "gongsunzhi": ["倒亂刃法", "鐵掌功", "藏邊大手印", "壁虎游牆"],
    "yelvqi": ["全真劍法", "全真心法", "草上飛"],
    "luwushuang": ["劈空掌", "基礎吐納", "雁行功"],
    "chengying": ["落英神劍", "落英神劍掌", "基礎吐納", "燕子三抄水"],
}

npc_ok = 0
for npc_key, skill_names in NPC_SKILLS.items():
    for skill_name in skill_names:
        if insert_npc_skill(npc_key, skill_name):
            npc_ok += 1
    print(f"  ✅ {npc_key}: {', '.join(skill_names)}")

print(f"\n✅ Done! {npc_ok} NPC skills inserted")
