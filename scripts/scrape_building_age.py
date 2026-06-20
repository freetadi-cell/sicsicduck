#!/usr/bin/env python3
"""
Scrape estate completion dates from Centaline.
For multi-phase estates, uses the LATEST phase's date.
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
            return json.loads(parsed)
        return parsed
    except:
        return raw

def search_and_get_date(estate_name, retry=3):
    """Search for estate on centanet, get the latest 入伙日期"""
    for attempt in range(retry):
        try:
            # Go to estate search page
            ab("open 'https://hk.centanet.com/estate/index'", timeout=30)
            time.sleep(2)
            
            # Fill search box
            ab(f'fill @e3 "{estate_name}"', timeout=15)
            time.sleep(2)
            
            # Get search results
            out, _, _ = ab("snapshot -i -c", timeout=15)
            
            # Find the first estate link (most relevant match)
            # Links look like: link "estate_name (area) 屋苑" [ref=eX]
            refs = re.findall(r'link "[^"]*屋苑"\s+\[ref=(\w+)\]', out)
            if not refs:
                # Try broader pattern
                refs = re.findall(r'link "[^"]*"\s+\[ref=(\w+)\]', out)
                # Filter to ones that look like estate links
                estate_links = []
                for ref in refs:
                    txt_out, _, _ = ab(f'get text @{ref}', timeout=10)
                    if estate_name in txt_out or '屋苑' in txt_out:
                        estate_links.append(ref)
                refs = estate_links[:1]
            
            if not refs:
                print(f"  ✗ No search results for {estate_name}")
                continue
            
            # Click the first result
            ab(f'click @{refs[0]}', timeout=15)
            time.sleep(3)
            
            # Extract the 入伙日期 from the page
            js = """
            const allText = document.body.innerText;
            const idx = allText.indexOf('入伙日期');
            if (idx < 0) JSON.stringify(null);
            else {
                // Get text around 入伙日期
                const around = allText.substring(Math.max(0, idx - 200), idx + 100);
                JSON.stringify(around);
            }
            """
            result = ab_eval(js)
            if not result:
                print(f"  ✗ No 入伙日期 found for {estate_name}")
                continue
            
            # Parse the date range - look for patterns like "1976年12月- 1987年5月"
            # Also handle "12/1976" format
            dates = []
            
            # Pattern 1: YYYY年MM月 - YYYY年MM月
            range_match = re.search(r'(\d{4})年(\d{1,2})月[-\s]+(\d{4})年(\d{1,2})月', result)
            if range_match:
                latest_year = int(range_match.group(3))
                latest_month = int(range_match.group(4))
                print(f"  ✓ {estate_name}: {range_match.group(0)} → latest: {latest_year}/{latest_month}")
                return latest_year
            
            # Pattern 2: MM/YYYY format (e.g., "12/1976")
            range_match2 = re.search(r'(\d{1,2}/\d{4})\s*[-到]\s*(\d{1,2}/\d{4})', result)
            if range_match2:
                latest = range_match2.group(2)
                latest_year = int(latest.split('/')[1])
                print(f"  ✓ {estate_name}: {range_match2.group(0)} → latest year: {latest_year}")
                return latest_year
            
            # Pattern 3: Single date like "1985年" or "1985"
            single_match = re.search(r'入伙日期[：:\s]*（?(\d{4})年?(\d{1,2})?月?', result)
            if single_match:
                year = int(single_match.group(1))
                print(f"  ✓ {estate_name}: {year}")
                return year
            
            # Pattern 4: Just find all years near 入伙日期
            year_matches = re.findall(r'(19\d{2}|20\d{2})年?', result)
            if year_matches:
                latest_year = max(int(y) for y in year_matches)
                print(f"  ~ {estate_name}: found years {year_matches} → latest: {latest_year}")
                return latest_year
            
            print(f"  ✗ Could not parse date for {estate_name}: {result[:100]}")
            return None
            
        except Exception as e:
            print(f"  ✗ Error for {estate_name} (attempt {attempt+1}): {e}")
            time.sleep(2)
    
    return None

def main():
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    
    estates = [e['name'] for e in data['estates']]
    print(f"Scraping 入伙日期 for {len(estates)} estates...\n")
    
    results = {}
    for i, name in enumerate(estates):
        print(f"[{i+1}/{len(estates)}] {name}")
        year = search_and_get_date(name)
        if year:
            results[name] = year
        time.sleep(1)  # Be polite
    
    # Save results
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scraped {len(results)}/{len(estates)} estates")
    missing = [e for e in estates if e not in results]
    if missing:
        print(f"⚠️ Missing: {missing}")

if __name__ == '__main__':
    main()
