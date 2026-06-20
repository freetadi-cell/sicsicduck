#!/usr/bin/env python3
"""
Scrape estate completion dates from Centaline estate pages.
For multi-phase estates, uses the LATEST phase's date.
Uses agent-browser to navigate and extract data from rendered pages.
"""
import subprocess, json, re, time, sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "rental_income.json"
OUTPUT = Path(__file__).parent.parent / "data" / "building_ages.json"

def ab(cmd, timeout=30):
    result = subprocess.run(f'agent-browser {cmd}', shell=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def ab_eval(js, timeout=20):
    js_safe = js.replace("'", "'\\''")
    result = subprocess.run(f"agent-browser eval '{js_safe}'", shell=True, capture_output=True, text=True, timeout=timeout)
    raw = result.stdout.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, str):
            return parsed
        return parsed
    except:
        return raw

def search_estate_code(estate_name):
    """Use the centanet API to find the estate typeCode"""
    import urllib.request
    url = "https://hk.centanet.com/estate/api/Estate/HotEstateSearch"
    data = json.dumps({"keyword": estate_name}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Referer': 'https://hk.centanet.com/estate/'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            # Find exact or closest match
            for item in result.get('data', []):
                if item.get('estateName') == estate_name:
                    return item.get('typeCode')
            # Fuzzy match - check if estate_name is in the result
            for item in result.get('data', []):
                name = item.get('estateName', '')
                if estate_name in name or name in estate_name:
                    return item.get('typeCode')
            return None
    except Exception as e:
        print(f"    API error: {e}")
        return None

def get_completion_date_from_page(type_code, estate_name):
    """Navigate to estate page and extract completion date from DOM"""
    from urllib.parse import quote
    url = f"https://hk.centanet.com/estate/{quote(estate_name)}/{type_code}"
    ab(f"open '{url}'", timeout=30)
    ab("wait 3000")
    
    # Extract the 入伙日期 text from the page
    js = r"""
    const allText = document.body.innerText;
    const idx = allText.indexOf('入伙日期');
    if (idx < 0) return JSON.stringify(null);
    return JSON.stringify(allText.substring(Math.max(0, idx - 300), idx + 50));
    """
    result = ab_eval(js)
    if not result or result == 'null':
        return None
    
    # Parse the date range
    # Pattern: "1976年12月- 1987年5月" or "12/1976" or single year
    range_match = re.search(r'(\d{4})年(\d{1,2})月[-\s–—]+(\d{4})年(\d{1,2})月', result)
    if range_match:
        latest_year = int(range_match.group(3))
        return latest_year
    
    # Pattern: MM/YYYY format
    range_match2 = re.search(r'(\d{1,2}/\d{4})\s*[-到直至]\s*(\d{1,2}/\d{4})', result)
    if range_match2:
        latest = range_match2.group(2)
        return int(latest.split('/')[1])
    
    # Single year
    single_match = re.search(r'(\d{4})年', result)
    if single_match:
        return int(single_match.group(1))
    
    # Find all years
    years = re.findall(r'(19\d{2}|20\d{2})', result)
    if years:
        return max(int(y) for y in years)
    
    return None

def main():
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    
    estates = [e['name'] for e in data['estates']]
    print(f"Total estates: {len(estates)}")
    
    # Load existing results
    results = {}
    if OUTPUT.exists():
        with open(OUTPUT, encoding='utf-8') as f:
            results = json.load(f)
        print(f"Already scraped: {len(results)}")
    
    remaining = [e for e in estates if e not in results]
    print(f"Remaining: {len(remaining)}\n")
    
    for i, name in enumerate(remaining):
        print(f"[{i+1}/{len(remaining)}] {name}")
        
        # Step 1: Get estate typeCode via API
        type_code = search_estate_code(name)
        if not type_code:
            print(f"  ✗ Could not find typeCode for {name}")
            continue
        print(f"  typeCode: {type_code}")
        
        # Step 2: Navigate to estate page and extract completion date
        year = get_completion_date_from_page(type_code, name)
        if year:
            results[name] = year
            print(f"  ✓ 入伙日期 latest year: {year}")
        else:
            print(f"  ✗ Could not extract date")
        
        # Save progress every 10 estates
        if (i + 1) % 10 == 0:
            with open(OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [Progress saved: {len(results)}/{len(estates)}]")
        
        time.sleep(0.5)
    
    # Final save
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    missing = [e for e in estates if e not in results]
    print(f"\n✅ Done: {len(results)}/{len(estates)} scraped")
    if missing:
        print(f"⚠️ Missing ({len(missing)}): {missing}")

if __name__ == '__main__':
    main()
