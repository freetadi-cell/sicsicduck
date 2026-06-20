#!/usr/bin/env python3
"""
Scrape estate completion dates from Centaline API.
Step 1: EstateAutoComplete to get typeCode
Step 2: GetEstateDetail to get maxOpDate (latest phase)
"""
import json, urllib.request, urllib.parse, time, sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "rental_income.json"
OUTPUT = Path(__file__).parent.parent / "data" / "building_ages.json"

HEADERS = {
    'Referer': 'https://hk.centanet.com/estate/',
    'User-Agent': 'Mozilla/5.0'
}

def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def search_estate(name):
    """Search estate to get typeCode"""
    encoded = urllib.parse.quote(name)
    url = f"https://hk.centanet.com/estate/api/Estate/EstateAutoComplete?keyword={encoded}"
    try:
        results = api_get(url)
        if not results:
            return None
        # Try exact match first
        for r in results:
            if r.get('displayName') == name:
                return r['typeCode']
        # Try contains match
        for r in results:
            if name in r.get('displayName', '') or r.get('displayName', '') in name:
                return r['typeCode']
        # Return first result
        return results[0].get('typeCode')
    except Exception as e:
        print(f"  Search error: {e}")
        return None

def get_estate_detail(type_code):
    """Get estate detail including maxOpDate"""
    url = f"https://hk.centanet.com/estate/api/Estate/GetEstateDetail?typeCode={type_code}&datasize=full"
    try:
        data = api_get(url)
        max_op = data.get('maxOpDate')
        min_op = data.get('minOpDate')
        if max_op:
            # maxOpDate is ISO format like "1981-06-18T00:00:00"
            year = int(max_op[:4])
            return year, min_op, max_op
        # Fallback: check buildingList for opDateYear
        buildings = data.get('buildingList', [])
        if buildings:
            years = [b.get('opDateYear', 0) for b in buildings if b.get('opDateYear')]
            if years:
                return max(years), min_op, max_op
        return None, min_op, max_op
    except Exception as e:
        print(f"  Detail error: {e}")
        return None, None, None

def main():
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    
    estates = [e['name'] for e in data['estates']]
    print(f"Total estates: {len(estates)}")
    
    # Load existing
    results = {}
    if OUTPUT.exists():
        with open(OUTPUT, encoding='utf-8') as f:
            results = json.load(f)
    
    remaining = [e for e in estates if e not in results]
    print(f"Remaining: {len(remaining)}\n")
    
    current_year = date.today().year
    
    for i, name in enumerate(remaining):
        print(f"[{i+1}/{len(remaining)}] {name}", end="")
        sys.stdout.flush()
        
        # Step 1: search
        type_code = search_estate(name)
        if not type_code:
            print(" ✗ no typeCode")
            continue
        
        # Step 2: get detail
        year, min_op, max_op = get_estate_detail(type_code)
        if year:
            results[name] = year
            age = current_year - year
            print(f" → {year} ({age}年)")
        else:
            print(f" ✗ no date (typeCode: {type_code})")
        
        # Save every 20
        if (i + 1) % 20 == 0:
            with open(OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [Saved {len(results)}/{len(estates)}]")
        
        time.sleep(0.3)
    
    # Final save
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    missing = [e for e in estates if e not in results]
    print(f"\n✅ Done: {len(results)}/{len(estates)} scraped")
    if missing:
        print(f"⚠️ Missing ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

if __name__ == '__main__':
    main()
