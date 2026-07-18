#!/usr/bin/env python3
"""
Generate daily deposit rates social media post and send to Telegram.
Reads from data/rates.json, formats a post, outputs to stdout and optionally sends via openclaw.
"""

import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "rates.json"

MEDAL_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_top5(banks, currency_key):
    """Get top 5 banks by best rate across all periods for given currency.
    Excludes exchange rates (currency conversion rates)."""
    PERIODS = ["1w", "1m", "2m", "3m", "4m", "6m", "9m", "12m"]
    PERIOD_NAMES = {
        "1w": "1星期", "1m": "1個月", "2m": "2個月",
        "3m": "3個月", "4m": "4個月", "6m": "6個月",
        "9m": "9個月", "12m": "12個月"
    }
    
    entries = []
    for b in banks:
        best_rate = None
        best_period = None
        best_note = ""
        
        for period in PERIODS:
            period_data = b[currency_key].get(period, {})
            
            # Check if new structure (has new_funds/existing_funds/exchange)
            if "new_funds" in period_data or "existing_funds" in period_data or "exchange" in period_data:
                # New structure - get best rate from new_funds or existing_funds only (skip exchange)
                for slot in ["new_funds", "existing_funds"]:
                    slot_data = period_data.get(slot, {})
                    rate = slot_data.get("rate")
                    if rate is not None and (best_rate is None or rate > best_rate):
                        best_rate = rate
                        best_period = period
                        note = slot_data.get("note", "")
                        if slot == "new_funds":
                            note = note + "（新資金）" if note else "新資金"
                        best_note = note
            else:
                # Old structure - skip if it's exchange rate
                conditions = period_data.get("conditions", [])
                if "exchange" in conditions:
                    continue
                
                rate = period_data.get("rate")
                if rate is not None and (best_rate is None or rate > best_rate):
                    best_rate = rate
                    best_period = period
                    fund_type = period_data.get("fund_type", "")
                    if fund_type == "new_funds":
                        best_note = "新資金"
                    else:
                        best_note = period_data.get("note", "")
        
        if best_rate is not None:
            period_name = PERIOD_NAMES.get(best_period, best_period)
            entries.append((b["name"], best_rate, period_name, best_note))
    
    entries.sort(key=lambda x: x[1], reverse=True)
    return entries[:5]


def format_top5(title, entries):
    """Format top 5 as ranked list."""
    lines = [f"\n📊 {title}"]
    i = 0
    while i < len(entries):
        name, rate, period, note = entries[i]
        # Check for ties
        tied = [entries[i]]
        j = i + 1
        while j < len(entries) and entries[j][1] == rate:
            tied.append(entries[j])
            j += 1
        
        medal = MEDAL_EMOJI[i] if i < len(MEDAL_EMOJI) else f"{i+1}."

        if len(tied) > 1:
            # Tie - show all with same medal
            medal = MEDAL_EMOJI[i] if i < len(MEDAL_EMOJI) else f"{i+1}."
            for t_name, t_rate, t_period, t_note in tied:
                note_str = f" {t_note}" if t_note else ""
                lines.append(f"{medal} {t_name} — {t_rate}% ({t_period})（並列第{i+1}）{note_str}")
        else:
            note_str = f" {note}" if note else ""
            lines.append(f"{medal} {name} — {rate}% ({period}){note_str}")
        
        i = j  # Skip past tied entries
    
    return "\n".join(lines)


def generate_post(data):
    """Generate the full social media post."""
    today = datetime.now().strftime("%Y年%-m月%-d日")
    banks = data["banks"]
    
    hkd_top5 = get_top5(banks, "hkd")
    usd_top5 = get_top5(banks, "usd")
    
    total_banks = len(banks)
    
    post = f"""🦆【{today}定期存款息率排行榜】邊間銀行最高息？

今日幫大家睇吓全港銀行最新定存息率，直接講重點👇
{format_top5("港元3個月定存 Top 5", hkd_top5)}
{format_top5("美元3個月定存 Top 5", usd_top5)}

💡 小貼士：
• 虛擬銀行嘅港元息率普遍比傳統銀行高，開戶又快又方便
• 美元定存息率整體高過港元，但要留意匯率風險
• 部分銀行嘅優惠息率只適用於新資金，記得睇清楚條款

🔗 完整{total_banks}間銀行息率比較：sicsicduck.com
📱 每日更新，bookmark 定輕鬆比較

#定期存款 #定存 #香港銀行 #利率比較 #食息鴨 #被動收入"""

    return post


def send_telegram(message):
    """Send message via openclaw CLI."""
    try:
        result = subprocess.run(
            ["openclaw", "message", "send", "--channel", "telegram", "-t", "telegram:885017126", "-m", message],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"Send failed: {result.stderr}", file=sys.stderr)
            return False
        print(f"Sent to Telegram successfully")
        return True
    except Exception as e:
        print(f"Send error: {e}", file=sys.stderr)
        return False


def main():
    data = load_data()
    post = generate_post(data)
    print(post)
    
    # If --send flag, also send to Telegram
    if "--send" in sys.argv:
        send_telegram(post)


if __name__ == "__main__":
    main()
