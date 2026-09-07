#!/usr/bin/env python3
"""
Add martial arts stats (武功/內功/輕功) to all NPCs and player template.
Values based on 神鵰俠侶 原著 ranking.

Scale: 1-100
  武功 (attack): offensive martial arts skill
  內功 (stamina/defense): internal energy / constitution
  輕功 (agility): movement / evasion skill
"""
import json
from pathlib import Path

WORLD_FILE = Path(__file__).parent.parent / "data" / "wulin_world.json"

# Based on 神鵰俠侶 power ranking
NPC_STATS = {
    # 五絕級
    "guojing":      {"martial": 92, "neigong": 90, "qinggong": 70},   # 郭靖 — 降龍十八掌剛猛，九陰真經內力深厚，輕功平平
    "zhoubotong":   {"martial": 95, "neigong": 88, "qinggong": 85},   # 周伯通 — 空明拳+雙手互搏，左右互搏無敵，輕功也不錯
    # 過兒係主角，後期超越五絕
    "yangguo":      {"martial": 94, "neigong": 85, "qinggong": 90},   # 楊過 — 玄鐵重劍大成，黯然銷魂掌，輕功了得
    "xiaolongnu":   {"martial": 80, "neigong": 82, "qinggong": 95},   # 小龍女 — 玉女心經，雙手互搏配合古墓輕功天下無雙
    # 頂級高手
    "liguomochou":  {"martial": 75, "neigong": 70, "qinggong": 88},   # 李莫愁 — 拂塵+冰魄銀針，古墓派輕功
    "gongsunzhi":   {"martial": 72, "neigong": 68, "qinggong": 70},   # 公孫止 — 陰陽倒亂刃，鐵掌功
    # 一流高手
    "huangrong":    {"martial": 78, "neigong": 72, "qinggong": 82},   # 黃蓉 — 打狗棒法+落英神劍掌，輕功聰明
    "yelvqi":       {"martial": 70, "neigong": 65, "qinggong": 72},   # 耶律齊 — 全真教武功
    # 二流
    "luwushuang":   {"martial": 45, "neigong": 40, "qinggong": 50},   # 陸無雙 — 基層武功
    "chengying":    {"martial": 50, "neigong": 45, "qinggong": 55},   # 程英 — 落英神劍掌有火候
}

# Player defaults (初入江湖)
PLAYER_STATS = {"martial": 10, "neigong": 10, "qinggong": 10}

def main():
    world = json.loads(WORLD_FILE.read_text(encoding="utf-8"))
    
    updated = 0
    for npc in world["npcs"]:
        key = npc["key"]
        if key in NPC_STATS:
            stats = NPC_STATS[key]
            npc["martial"] = stats["martial"]
            npc["neigong"] = stats["neigong"]
            npc["qinggong"] = stats["qinggong"]
            updated += 1
            print(f"✅ {npc['name']}：武功{stats['martial']} 內功{stats['neigong']} 輕功{stats['qinggong']}")
        else:
            print(f"⚠️ {npc['name']} ({key})：無配置，跳過")
    
    WORLD_FILE.write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已更新 {updated}/{len(world['npcs'])} 位 NPC")
    print(f"玩家預設：武功{PLAYER_STATS['martial']} 內功{PLAYER_STATS['neigong']} 輕功{PLAYER_STATS['qinggong']}")

if __name__ == "__main__":
    main()
