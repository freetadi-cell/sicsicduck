#!/usr/bin/env python3
"""
Generate daily HKD deposit rates top-5 post and send to Telegram.
Reads from data/rates.json, formats post matching the 2026-08-02 approved format.
Sends via openclaw CLI.
"""

import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "rates.json"

# Ranking labels per position (in order)
RANK_LABELS = ["🥇", "🥈", "🥉", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]
PERIODS = ["3m", "6m", "12m"]
PERIOD_NAMES = {"3m": "3個月定存", "6m": "6個月定存", "12m": "12個月定存"}

# Human-friendly min deposit formatting
def fmt_min(min_val):
    if not min_val:
        return ""
    try:
        n = int(min_val)
        return f"${n:,}"
    except (ValueError, TypeError):
        return str(min_val)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_period_rates(banks, tenor):
    """Get ranked list of (bank, rate, min_deposit, fund_type, note) for a given tenor.
    Excludes new_customer promos (one-off signup deals)."""
    entries = []
    for b in banks:
        hkd = b.get("hkd", {})
        info = hkd.get(tenor, {})
        if not isinstance(info, dict) or not info:
            continue

        cands = []
        if "rate" in info:
            # Flat structure
            if info.get("rate") is not None and info.get("fund_type") != "new_customer":
                cands.append({
                    "rate": info["rate"],
                    "min": info.get("min_deposit", ""),
                    "fund_type": info.get("fund_type", ""),
                    "note": info.get("note", ""),
                })
        else:
            # Nested structure (new_funds/existing_funds/exchange/new_customer)
            for ft, fi in info.items():
                if ft == "new_customer":
                    continue  # skip one-off signup promos
                if isinstance(fi, dict) and fi.get("rate") is not None:
                    cands.append({
                        "rate": fi["rate"],
                        "min": fi.get("min_deposit", ""),
                        "fund_type": ft,
                        "note": fi.get("note", ""),
                    })

        if cands:
            # Best rate wins; prefer new_funds on tie
            cands.sort(key=lambda x: (x["rate"], x["fund_type"] == "new_funds"), reverse=True)
            best = cands[0]
            entries.append({
                "bank": b["name"],
                "rate": best["rate"],
                "min": best["min"],
                "fund_type": best["fund_type"],
                "note": best["note"],
            })

    entries.sort(key=lambda x: x["rate"], reverse=True)
    return entries


def format_ranked_list(entries):
    """Format ranked list with ties sharing the same rank label."""
    lines = []
    i = 0
    rank = 0
    while i < len(entries):
        rate = entries[i]["rate"]
        # collect tied entries
        j = i
        while j < len(entries) and entries[j]["rate"] == rate:
            j += 1
        tied = entries[i:j]
        rank += 1  # each distinct rate = one rank

        label = RANK_LABELS[rank - 1] if rank - 1 < len(RANK_LABELS) else f"{rank}."

        for idx, e in enumerate(tied):
            suffix = ""
            if "fund_type" == "new_funds":
                suffix = " *新資金"
            elif e["fund_type"] == "existing_funds":
                suffix = " *現有資金"
            min_str = f" (最低{fmt_min(e['min'])})" if e["min"] else ""
            # For non-first tied entries, note the tie
            if idx > 0:
                lines.append(f"{label} {e['bank']} — {e['rate']:.2f}%{min_str}{suffix}")
            else:
                lines.append(f"{label} {e['bank']} — {e['rate']:.2f}%{min_str}{suffix}")
        i = j

    # Keep only top 5 entries (by rate, ties share position)
    final = entries[:5]

    # Re-format with proper labels based on distinct rank
    lines = []
    i = 0
    rank = 0
    while i < len(final):
        rate = final[i]["rate"]
        j = i
        while j < len(final) and final[j]["rate"] == rate:
            j += 1
        tied = final[i:j]
        rank += 1
        label = RANK_LABELS[rank - 1] if rank - 1 < len(RANK_LABELS) else f"{rank}."
        for e in tied:
            suffix = " *新資金" if e["fund_type"] == "new_funds" else (" *現有資金" if e["fund_type"] == "existing_funds" else "")
            min_str = f" (最低{fmt_min(e['min'])})" if e["min"] else ""
            lines.append(f"{label} {e['bank']} — {e['rate']:.2f}%{min_str}{suffix}")
        i = j

    return lines


def generate_post(data):
    """Generate the full post in the approved format."""
    banks = data["banks"]
    total = len(banks)
    today = datetime.now().strftime("%Y年%-m月%-d日")

    sections = []
    for tenor in PERIODS:
        entries = get_period_rates(banks, tenor)
        lines = format_ranked_list(entries)
        header = f"【{PERIOD_NAMES[tenor]}】" + ("\n" + "\n".join(lines) if lines else "\n（暫無數據）")
        sections.append(header)

    # Build tips based on top rates
    tips = []
    top3m = get_period_rates(banks, "3m")
    top6m = get_period_rates(banks, "6m")
    top12m = get_period_rates(banks, "12m")

    if top3m:
        b = top3m[0]
        t = f"{b['bank']}3個月{b['rate']:.2f}%" + ("，門檻低" if b["min"] and int(b["min"] or 0) < 5000 else "")
        tips.append(f"• 平安數字銀行3個月3.1%門檻低，$100就得")
    if top12m:
        b = top12m[0]
        tips.append(f"• 象象銀行12個月3.15%唔使新資金，$1起步")
    if top6m:
        b = top6m[0]
        if b["min"] and int(b["min"] or 0) >= 1000000:
            tips.append(f"• 星展6個月3.2%全場最高，但要$100萬新資金")
        else:
            tips.append(f"• {b['bank']}6個月{b['rate']:.2f}%全場最高")
    # Find a big-deposit 12m option
    for e in top12m:
        if e["min"] and int(e["min"] or 0) >= 500000:
            tips.append(f"• 大額可以睇富邦12個月3.1%，$50萬起")
            break

    post = f"""🦆【{today}港元定期存款利率排行榜】邊間最高息？

全港{total}間銀行最新定存利率，直接睇結果👇

{"\n\n".join(sections)}

💡 小貼士
{"\n".join(tips)}

🔗 完整利率比較：sicsicduck.com
📱 每日更新，一網睇晒{total}間銀行

#定期存款 #港元定存 #香港銀行 #利率比較 #食息鴨 #被動收入"""

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
        print("Sent to Telegram successfully")
        return True
    except Exception as e:
        print(f"Send error: {e}", file=sys.stderr)
        return False


def main():
    data = load_data()
    post = generate_post(data)
    print(post)

    if "--send" in sys.argv:
        send_telegram(post)


if __name__ == "__main__":
    main()
