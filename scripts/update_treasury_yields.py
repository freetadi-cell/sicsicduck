#!/usr/bin/env python3
"""
Fetch US Treasury yields from U.S. Treasury Department (treasury.gov)
Updates every 10 minutes via cron
Stores 30 days history
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
YIELDS_FILE = DATA_DIR / "treasury_yields.json"

# Maturities to fetch (ordered)
MATURITIES = ["3M", "2Y", "5Y", "10Y", "30Y"]


def fetch_yields_from_treasury_gov():
    """Fetch all treasury yields from treasury.gov"""
    print("Fetching US Treasury yields from treasury.gov...")
    
    yields = {}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            try:
                url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2026"
                print(f"  Fetching {url}")
                page.goto(url, timeout=30000, wait_until='domcontentloaded')
                time.sleep(2)
                
                # Extract all yields using JavaScript
                data = page.evaluate('''() => {
                    const tables = document.querySelectorAll('table');
                    if (tables.length < 2) return null;
                    
                    const table = tables[1];
                    const rows = table.querySelectorAll('tr');
                    
                    if (rows.length < 2) return null;
                    
                    // Parse header row to find column indices
                    const headerCells = rows[0].querySelectorAll('th, td');
                    const headers = Array.from(headerCells).map(cell => cell.textContent.trim());
                    
                    // Map header names to maturity codes
                    const maturityMap = {
                        '1 Mo': '1M',
                        '1.5 Mo': '1.5M',
                        '2 Mo': '2M',
                        '3 Mo': '3M',
                        '4 Mo': '4M',
                        '6 Mo': '6M',
                        '1 Yr': '1Y',
                        '2 Yr': '2Y',
                        '3 Yr': '3Y',
                        '5 Yr': '5Y',
                        '7 Yr': '7Y',
                        '10 Yr': '10Y',
                        '20 Yr': '20Y',
                        '30 Yr': '30Y'
                    };
                    
                    // Find column indices for our target maturities
                    const colIndices = {};
                    for (let i = 0; i < headers.length; i++) {
                        const h = headers[i];
                        if (maturityMap[h]) {
                            colIndices[maturityMap[h]] = i;
                        }
                    }
                    
                    // Get first data row (most recent)
                    const dataCells = rows[1].querySelectorAll('td');
                    const dateCell = dataCells[0]?.textContent.trim();
                    
                    // Extract yields
                    const yields = {};
                    for (const [maturity, colIdx] of Object.entries(colIndices)) {
                        if (colIdx !== undefined && dataCells[colIdx]) {
                            yields[maturity] = dataCells[colIdx].textContent.trim();
                        }
                    }
                    
                    return { date: dateCell, yields: yields };
                }''')
                
                if data and data.get('yields'):
                    print(f"  Date: {data.get('date', 'N/A')}")
                    
                    # Extract our target maturities
                    for maturity in MATURITIES:
                        value = data['yields'].get(maturity)
                        if value:
                            try:
                                yield_val = float(value)
                                yields[maturity] = {
                                    "yield": round(yield_val, 3),
                                    "ticker": "treasury.gov",
                                    "source": "U.S. Treasury"
                                }
                                print(f"    {maturity}: {yield_val:.3f}%")
                            except ValueError:
                                print(f"    {maturity}: parse error ({value})")
                        else:
                            print(f"    {maturity}: not found")
                else:
                    print("  Could not extract data from treasury.gov")
            
            finally:
                browser.close()
    
    except Exception as e:
        print(f"  Error fetching from treasury.gov: {e}")
    
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
        "source": "U.S. Treasury Department (treasury.gov)",
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
        
        # Get yields for each maturity (ordered by maturity: 3M, 2Y, 5Y, 10Y, 30Y)
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
    yields = fetch_yields_from_treasury_gov()
    
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