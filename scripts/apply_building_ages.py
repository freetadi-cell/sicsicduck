#!/usr/bin/env python3
"""Update rental_income.json with scraped building ages from Centaline"""
import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RENTAL_FILE = DATA_DIR / "rental_income.json"
AGES_FILE = DATA_DIR / "building_ages.json"

current_year = date.today().year

with open(RENTAL_FILE, encoding='utf-8') as f:
    rental = json.load(f)

with open(AGES_FILE, encoding='utf-8') as f:
    ages = json.load(f)

updated = 0
missing = []
for estate in rental['estates']:
    name = estate['name']
    if name in ages:
        year = ages[name]
        estate['completion_year'] = year
        estate['building_age'] = current_year - year
        updated += 1
    else:
        missing.append(name)

with open(RENTAL_FILE, 'w', encoding='utf-8') as f:
    json.dump(rental, f, ensure_ascii=False, indent=2)

print(f"✅ Updated {updated}/{len(rental['estates'])} estates")
if missing:
    print(f"⚠️ Missing: {missing}")
