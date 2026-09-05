#!/usr/bin/env python3
"""
update_wulin.py — Wulin Project 世界推進引擎（delta 模式）

用 kimi-k3 模擬 NPC 之間嘅互動 + 時間流逝，每日演化世界。
AI 只輸出「變化」（delta），Python 合併入世界 JSON——快、平、唔怕截斷。

版面 wulin.html（靜態）讀 data/wulin_world.json 顯示世界。

用法：
    ./venv/bin/python3 scripts/update_wulin.py          # 推進一日 + git push
    ./venv/bin/python3 scripts/update_wulin.py --dry    # 只顯示 delta 唔寫檔
"""
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
WORLD_FILE = ROOT / "data" / "wulin_world.json"

OPENCLAW_CFG = Path("/home/freet/.openclaw/openclaw.json")
API_BASE = "https://yuanyuaicloud.cn/v1"
API_MODEL = "kimi-k3"


def get_api_key():
    with open(OPENCLAW_CFG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["models"]["providers"]["yuanyuai"]["apiKey"]


def call_kimi(api_key, sys_prompt, user_prompt, max_tokens=4000):
    payload = json.dumps({
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=360) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


SYS_PROMPT = """你係金庸《神鵰俠侶》世界嘅「天命」——負責推進江湖一日嘅敘事者。

讀完而家嘅世界狀態，推進一日，只輸出「變化」（delta），唔使重複冇變嘅嘢：

{
  "world_time": "第X日 · 暮春",
  "events": [
    {"day": 2, "text": "江湖大事描述", "npcs": ["相關npc_key"]}
  ],
  "npc_updates": {
    "npc_key": {
      "mood": "新心境（有變先寫）",
      "attitude": "新待人態度（有變先寫）",
      "dialogue": ["三句最新台詞", "…", "…"],
      "affinity_delta": 0,
      "alignment_delta": 0,
      "relation_deltas": {"其他npc_key": -2}
    }
  },
  "chat_options": {
    "npc_key": [
      {"say": "玩家開口講嘅一句話", "reply": "NPC 嘅即時回應", "affinity_delta": 1, "alignment_delta": 0}
    ]
  }
}

【規則】
1. NPC 之間自然互動（楊過與小龍女、郭靖黃蓉守襄陽、李莫愁作惡、金輪法王圖謀…），有互動嘅 NPC 先出現喺 npc_updates
2. dialogue 用廣東話書面語，完全符合角色性格同最近經歷，三句
3. affinity_delta 係 NPC 對玩家好感嘅變化（-3 至 +3，通常 0；玩家冇出現就多數 0）
4. alignment_delta 係玩家講嗰句嘢令佢嘅善惡值變化（-3 至 +3，0=冇影響）。正派行為（守城、勸善、為民）+，邪惡行為（背叛、挑撥、辱罵長輩）-
5. relation_deltas 係 NPC 之間交情變化（-5 至 +5），有先寫
5. 新增 1-3 條 events，要同之前嘅事件敘事連貫（世界有歷史感）
6. 忠於原著人物性格、武功、關係
7. 玩家係「無名少年」，NPC 對玩家嘅好感主要由玩家行為影響，NPC 互動只輕微帶動
7. chat_options：每位 NPC 都要俾 3 個選項——「玩家可以開口講嘅話」，廣東話口語 8-20 字，語氣各有不同（恭維／直言相勸／打探消息／挑釁／求助……自由配搭，貼合 NPC 身份）
8. reply 係 NPC 聽完嗰句嘅即時回應，廣東話 15-40 字，貼合佢性格同當前心境；affinity_delta（-5 至 +5）反映嗰句令 NPC 幾受落——三句效果要拉開明顯差距（例如 +5 / +1 / -3），唔好全部一樣
9. alignment_delta（-3 至 +3）係玩家講嗰句嘢反映嘅善惡立場——三句要有拉開：一句正派、一句中立、一句邪惡（例如 +2 / 0 / -2）
10. 只輸出 JSON，唔好 markdown fence、唔好解釋"""


def strip_fences(txt):
    txt = txt.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```\w*\n?", "", txt)
        txt = re.sub(r"\n?```$", "", txt)
    return txt


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(v)))


def apply_delta(world, delta):
    """合併 AI delta 入世界 JSON，原地修改並返回"""
    meta = world["meta"]
    meta["world_time"] = str(delta.get("world_time") or meta.get("world_time"))

    events = world.get("events", [])
    for e in delta.get("events", []) or []:
        if isinstance(e, dict) and e.get("text"):
            events.append({
                "day": int(e.get("day", 1)),
                "text": str(e["text"]),
                "npcs": list(e.get("npcs", []) or []),
            })
    world["events"] = events[-40:]  # 保留最近 40 條，避免 JSON 無限脹

    npcs = {n["key"]: n for n in world["npcs"]}
    for key, up in (delta.get("npc_updates") or {}).items():
        n = npcs.get(key)
        if not n:
            print(f"  ⚠️ 未知 NPC key：{key}（跳過）")
            continue
        if up.get("mood"):
            n["mood"] = str(up["mood"])
        if up.get("attitude"):
            n["attitude"] = str(up["attitude"])
        dlg = up.get("dialogue")
        if isinstance(dlg, list) and dlg:
            n["dialogue"] = [str(d) for d in dlg][:3]
        try:
            n["affinity"] = clamp(n.get("affinity", 0) + int(up.get("affinity_delta", 0)))
        except (TypeError, ValueError):
            pass
        try:
            n["alignment"] = clamp(n.get("alignment", 500) + int(up.get("alignment_delta", 0)), 0, 1000)
        except (TypeError, ValueError):
            pass
        rels = n.setdefault("relations", {})
        for k2, dv in (up.get("relation_deltas") or {}).items():
            try:
                rels[k2] = clamp(rels.get(k2, 50) + int(dv))
            except (TypeError, ValueError):
                pass

    # 玩家對話選項：每位 NPC 三句「可以講嘅話」+ NPC 回應 + 好感效果
    for key, arr in (delta.get("chat_options") or {}).items():
        n = npcs.get(key)
        if not n:
            print(f"  ⚠️ 未知 NPC key（chat_options）：{key}（跳過）")
            continue
        cleaned = []
        for o in arr if isinstance(arr, list) else []:
            if isinstance(o, dict) and o.get("say") and o.get("reply"):
                try:
                    d = max(-5, min(5, int(o.get("affinity_delta", 0))))
                except (TypeError, ValueError):
                    d = 0
                cleaned.append({"say": str(o["say"])[:60],
                                "reply": str(o["reply"])[:150],
                                "affinity_delta": d,
                                "alignment_delta": max(-3, min(3, int(o.get("alignment_delta", 0))))})
        if cleaned:
            n["chat_options"] = cleaned[:3]
    return world


def git_push():
    for cmd in (
        ["git", "add", "data/wulin_world.json"],
        ["git", "commit", "-m",
         f"Wulin: world advances to {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push", "origin", "master"],
    ):
        subprocess.run(cmd, cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    dry = "--dry" in sys.argv
    api_key = get_api_key()
    world = json.loads(WORLD_FILE.read_text(encoding="utf-8"))
    print(f"而家世界：{world['meta'].get('world_time')} · {len(world['npcs'])} 位 NPC · {len(world.get('events', []))} 條事件")

    user_prompt = ("而家嘅世界狀態 JSON：\n"
                   + json.dumps(world, ensure_ascii=False)
                   + "\n\n請推進一日，只輸出 delta JSON。")

    delta = None
    # kimi-k3 係 reasoning 模型：先燒 token 思考先寫 content，max_tokens 太細會空回覆
    for attempt, mt in enumerate([8000, 12000, 20000], 1):
        try:
            content = call_kimi(api_key, SYS_PROMPT, user_prompt, max_tokens=mt)
            if not content:
                raise ValueError("content 空（reasoning 燒盡 max_tokens）")
            delta = json.loads(strip_fences(content))
            if not isinstance(delta, dict):
                raise ValueError("delta not dict")
            break
        except Exception as e:
            print(f"  attempt {attempt} 失敗：{e}")
            if attempt == 3:
                print("❌ 三次嘗試都失敗，今輪唔推進（世界保持原狀）")
                sys.exit(1)

    world = apply_delta(world, delta)
    print(f"✅ 推進至：{world['meta'].get('world_time')}")
    for e in world.get("events", [])[-3:]:
        print(f"   第{e['day']}日 · {e['text']}")
    n_opts = sum(len(n.get("chat_options", [])) for n in world["npcs"])
    n_has = sum(1 for n in world["npcs"] if n.get("chat_options"))
    print(f"   對話選項：{n_opts} 條（{n_has}/{len(world['npcs'])} 位 NPC）")

    if dry:
        print("（dry run，唔寫檔）")
        return

    world["meta"]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    WORLD_FILE.write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        git_push()
        print("✅ git commit + push 完成")
    except Exception as e:
        print(f"⚠️ git push 失敗：{e}（JSON 已更新本地）")
        sys.exit(1)


if __name__ == "__main__":
    main()
