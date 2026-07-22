#!/usr/bin/env python3
"""
Fetch US Treasury YIELDS from FRED (Federal Reserve Economic Data)
Updates every 10 minutes via cron
Stores 30 days history

Data source: FRED - Market Yield on US Treasury Securities
- DGS3MO: 3-Month Treasury Yield
- DGS2: 2-Year Treasury Yield
- DGS5: 5-Year Treasury Yield
- DGS10: 10-Year Treasury Yield
- DGS30: 30-Year Treasury Yield
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
YIELDS_FILE = DATA_DIR / "treasury_yields.json"

# FRED Series IDs for Treasury Yields
FRED_SERIES = ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"]
MATURITIES = ["3M", "2Y", "5Y", "10Y", "30Y"]


def fetch_yields_from_fred():
    """Fetch Treasury yields from FRED CSV using curl"""
    print("Fetching US Treasury yields from FRED...")
    
    yields = {}
    
    try:
        # Build FRED CSV URL
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
               f"?id={','.join(FRED_SERIES)}"
               f"&cosd={start_date.strftime('%Y-%m-%d')}"
               f"&coed={end_date.strftime('%Y-%m-%d')}")
        
        print(f"  Fetching FRED CSV...")
        
        # Use curl to download CSV (most reliable method)
        result = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-L", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"  Error: curl failed with code {result.returncode}")
            return yields
        
        csv_text = result.stdout
        lines = csv_text.strip().split('\n')
        
        if len(lines) < 2:
            print("  Error: No data returned")
            return yields
        
        # Parse header to get series order
        header = lines[0].split(',')
        series_list = [s.strip() for s in header[1:]]  # Skip date column
        
        print(f"  Series found: {series_list}")
        
        # Get last non-empty row
        for line in reversed(lines[1:]):
            parts = line.split(',')
            if len(parts) >= 6:
                # Check if all values are valid
                valid = all(p.strip() and p.strip() != '.' for p in parts[1:])
                if valid:
                    date = parts[0].strip()
                    print(f"  Date: {date}")
                    
                    for i, series_id in enumerate(series_list):
                        value = parts[i + 1].strip()
                        # Map series to maturity
                        for j, sid in enumerate(FRED_SERIES):
                            if sid == series_id:
                                maturity = MATURITIES[j]
                                yields[maturity] = {
                                    "yield": round(float(value), 3),
                                    "date": date,
                                    "series": series_id,
                                    "source": "FRED (Federal Reserve)"
                                }
                                print(f"    {maturity}: {value}%")
                                break
                    break
        
        if not yields:
            print("  Warning: Could not parse yield data")
        
    except subprocess.TimeoutExpired:
        print("  Error: curl timeout (30s)")
    except Exception as e:
        print(f"  Error: {e}")
    
    return yields


def save_yields(yields):
    """Save yields to JSON file with 30 days history"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing history
    history = []
    if YIELDS_FILE.exists():
        try:
            with open(YIELDS_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                history = old_data.get("history", [])
        except:
            history = []
    
    # Add today's data to history
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Remove old entry for today if exists
    history = [h for h in history if h.get("date") != today_str]
    
    # Add new entry
    history_entry = {
        "date": today_str,
        "yields": yields
    }
    history.append(history_entry)
    
    # Keep only last 30 days
    history = sorted(history, key=lambda x: x["date"], reverse=True)[:30]
    
    # Save
    data = {
        "last_updated": datetime.now().isoformat(),
        "timezone": "Asia/Hong_Kong",
        "source": "FRED - Federal Reserve Bank of St. Louis",
        "description": "Market Yield on US Treasury Securities",
        "current": yields,
        "history": history,
        "cache_duration_minutes": 10
    }
    
    with open(YIELDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved yields to {YIELDS_FILE}")
    print(f"History: {len(history)} days")


def update_html_page():
    """Update treasury-yields.html with latest data"""
    html_path = SCRIPT_DIR.parent / "treasury-yields.html"
    
    # Read current HTML
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Read yields data
    with open(YIELDS_FILE, "r", encoding="utf-8") as f:
        yields_data = json.load(f)
    
    # Generate history table rows
    history = yields_data.get("history", [])
    table_rows = ""
    
    for entry in history:
        date_str = entry.get("date", "--")
        yields = entry.get("yields", {})
        
        # Format date (YYYY-MM-DD -> DD/MM)
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d/%m")
        except:
            formatted_date = date_str
        
        # Get yields for each maturity
        y3m = yields.get("3M", {}).get("yield", "--")
        y2y = yields.get("2Y", {}).get("yield", "--")
        y5y = yields.get("5Y", {}).get("yield", "--")
        y10y = yields.get("10Y", {}).get("yield", "--")
        y30y = yields.get("30Y", {}).get("yield", "--")
        
        table_rows += f'''            <tr>
                <td>{formatted_date}</td>
                <td class="rate-cell">{y3m if y3m == "--" else f"{y3m:.3f}%"}</td>
                <td class="rate-cell">{y2y if y2y == "--" else f"{y2y:.3f}%"}</td>
                <td class="rate-cell">{y5y if y5y == "--" else f"{y5y:.3f}%"}</td>
                <td class="rate-cell">{y10y if y10y == "--" else f"{y10y:.3f}%"}</td>
                <td class="rate-cell">{y30y if y30y == "--" else f"{y30y:.3f}%"}</td>
            </tr>
'''
    
    # Replace table body
    import re
    pattern = r'<tbody id="historyBody">.*?</tbody>'
    replacement = f'''<tbody id="historyBody">
{table_rows}        </tbody>'''
    
    new_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # Update last updated time in HTML
    last_updated = yields_data["last_updated"]
    pattern_time = r'<span id="lastUpdated">.*?</span>'
    replacement_time = f'<span id="lastUpdated">{last_updated[:19]}</span>'
    new_html = re.sub(pattern_time, replacement_time, new_html)
    
    # Update hero update time
    pattern_hero = r'id="heroUpdateTime">.*?</div>'
    replacement_hero = f'id="heroUpdateTime">最後更新: {last_updated[:19]}</div>'
    new_html = re.sub(pattern_hero, replacement_hero, new_html)
    
    # Update summary cards
    current = yields_data.get("current", {})
    
    # Update yield values in summary cards
    pattern_3m = r'<div class="value" id="yield3m">.*?</div>'
    replacement_3m = f'<div class="value" id="yield3m">{current.get("3M", {}).get("yield", "--")}%</div>'
    new_html = re.sub(pattern_3m, replacement_3m, new_html)
    
    pattern_2y = r'<div class="value" id="yield2y">.*?</div>'
    replacement_2y = f'<div class="value" id="yield2y">{current.get("2Y", {}).get("yield", "--")}%</div>'
    new_html = re.sub(pattern_2y, replacement_2y, new_html)
    
    pattern_5y = r'<div class="value" id="yield5y">.*?</div>'
    replacement_5y = f'<div class="value" id="yield5y">{current.get("5Y", {}).get("yield", "--")}%</div>'
    new_html = re.sub(pattern_5y, replacement_5y, new_html)
    
    pattern_10y = r'<div class="value" id="yield10y">.*?</div>'
    replacement_10y = f'<div class="value" id="yield10y">{current.get("10Y", {}).get("yield", "--")}%</div>'
    new_html = re.sub(pattern_10y, replacement_10y, new_html)
    
    pattern_30y = r'<div class="value" id="yield30y">.*?</div>'
    replacement_30y = f'<div class="value" id="yield30y">{current.get("30Y", {}).get("yield", "--")}%</div>'
    new_html = re.sub(pattern_30y, replacement_30y, new_html)
    
    # Write updated HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"Updated {html_path}")


def main():
    yields = fetch_yields_from_fred()
    
    if not yields:
        print("No yields fetched!")
        return
    
    save_yields(yields)
    update_html_page()
    
    # Commit and push to GitHub (only if there are changes)
    import subprocess
    
    # Add files
    subprocess.run(["git", "add", "data/treasury_yields.json", "treasury-yields.html"], cwd=SCRIPT_DIR.parent)
    
    # Check if there are changes
    result = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=SCRIPT_DIR.parent, capture_output=True)
    has_changes = result.returncode != 0
    
    if has_changes:
        # Commit
        subprocess.run(["git", "commit", "-m", f"Auto: treasury yields {datetime.now().strftime('%Y-%m-%d %H:%M')}"], cwd=SCRIPT_DIR.parent)
        
        # Pull with rebase to avoid conflicts
        subprocess.run(["git", "pull", "--rebase", "origin", "master"], cwd=SCRIPT_DIR.parent, capture_output=True)
        
        # Push
        push_result = subprocess.run(["git", "push", "origin", "master"], cwd=SCRIPT_DIR.parent, capture_output=True, text=True)
        
        if push_result.returncode == 0:
            print("\nTreasury yields updated and pushed to GitHub!")
        else:
            print(f"\nWarning: Git push failed: {push_result.stderr}")
    else:
        print("\nNo changes to commit (yields unchanged)")


if __name__ == "__main__":
    main()