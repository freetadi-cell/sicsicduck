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
    """Get top 5 banks by 3m rate for given currency."""
    entries = []
    for b in banks:
        rate_info = b[currency_key].get("3m", {})
        rate = rate_info.get("rate")
        if rate is not None:
            entries.append((b["name"], rate, rate_info.get("note", "")))
    entries.sort(key=lambda x: x[1], reverse=True)
    return entries[:5]


def format_top5(title, entries):
    """Format top 5 as ranked list."""
    lines = [f"\n📊 {title}"]
    i = 0
    while i < len(entries):
        name, rate, note = entries[i]
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
            for t_name, t_rate, t_note in tied:
                lines.append(f"{medal} {t_name} — {t_rate}%（並列第{i+1}）")
        else:
            lines.append(f"{medal} {name} — {rate}%")
        
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
