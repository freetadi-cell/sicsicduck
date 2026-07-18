#!/usr/bin/env python3
"""
Fetch US Treasury yields from Yahoo Finance
Updates every 10 minutes via cron
"""

import json
import yfinance as yf
from datetime import datetime
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
YIELDS_FILE = DATA_DIR / "treasury_yields.json"

# Treasury yield tickers
YIELD_TICKERS = {
    "1M": "^IRX",    # 13 Week Treasury Bill
    "3M": "^IRX",    # 13 Week Treasury Bill (same as 1M)
    "6M": "TUZ=F",   # 6 Month Treasury Bill Futures
    "1Y": "^FVX",    # 5 Year Treasury Note (proxy)
    "2Y": "^FVX",    # 5 Year Treasury Note
    "5Y": "^FVX",    # 5 Year Treasury Note
    "7Y": "^FVX",    # 5 Year Treasury Note (proxy)
    "10Y": "^TNX",   # 10 Year Treasury Note
    "20Y": "^TYX",   # 30 Year Treasury Bond (proxy)
    "30Y": "^TYX",   # 30 Year Treasury Bond
}

def fetch_yields():
    """Fetch current treasury yields from Yahoo Finance"""
    print("Fetching US Treasury yields from Yahoo Finance...")
    
    yields = {}
    
    # Fetch main yields
    main_tickers = {
        "3M": "^IRX",    # 3 Month
        "2Y": "^FVX",    # 2 Year (using 5Y as proxy)
        "5Y": "^FVX",    # 5 Year
        "10Y": "^TNX",   # 10 Year
        "30Y": "^TYX",   # 30 Year
    }
    
    for maturity, ticker in main_tickers.items():
        try:
            print(f"  Fetching {maturity} ({ticker})...")
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            
            if not hist.empty:
                close_price = hist['Close'].iloc[-1]
                yields[maturity] = {
                    "yield": round(float(close_price), 3),
                    "ticker": ticker,
                    "source": "Yahoo Finance"
                }
                print(f"    {maturity}: {close_price:.3f}%")
            else:
                print(f"    No data for {maturity}")
                
        except Exception as e:
            print(f"    Error fetching {maturity}: {e}")
    
    return yields

def save_yields(yields):
    """Save yields to JSON file"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "last_updated": datetime.now().isoformat(),
        "timezone": "Asia/Hong_Kong",
        "yields": yields,
        "cache_duration_minutes": 10
    }
    
    with open(YIELDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved yields to {YIELDS_FILE}")

def update_html_page():
    """Update treasury-yields.html with latest data"""
    html_path = SCRIPT_DIR.parent / "treasury-yields.html"
    
    # Read current HTML
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Read yields data
    with open(YIELDS_FILE, "r", encoding="utf-8") as f:
        yields_data = json.load(f)
    
    # Generate yield cards HTML
    yields_html = ""
    for maturity, data in yields_data["yields"].items():
        yield_value = data["yield"]
        yields_html += f'''            <div class="yield-card">
                <div class="yield-maturity">{maturity}</div>
                <div class="yield-value">{yield_value:.3f}%</div>
            </div>
'''
    
    # Replace yields grid content
    import re
    pattern = r'<div class="yields-grid" id="yieldsGrid">.*?</div>\s*</div>\s*<!-- Yield Curve Info -->'
    replacement = f'''<div class="yields-grid" id="yieldsGrid">
{yields_html}        </div>
        <!-- Yield Curve Info -->'''
    
    new_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # Update last updated time in HTML
    last_updated = yields_data["last_updated"]
    pattern_time = r'<span id="lastUpdated">.*?</span>'
    replacement_time = f'<span id="lastUpdated">{last_updated[:19]}</span>'
    new_html = re.sub(pattern_time, replacement_time, new_html)
    
    # Write updated HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    print(f"Updated {html_path}")

def main():
    yields = fetch_yields()
    
    if not yields:
        print("No yields fetched!")
        return
    
    save_yields(yields)
    update_html_page()
    
    print("\nTreasury yields updated successfully!")

if __name__ == "__main__":
    main()