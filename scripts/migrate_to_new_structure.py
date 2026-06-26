#!/usr/bin/env python3
"""
數據結構遷移腳本 - 將 rates.json 從舊結構轉換為新結構

舊結構：
{
  "hkd": {
    "3m": {
      "rate": 3.0,
      "fund_type": "new_funds",
      "conditions": []
    }
  }
}

新結構：
{
  "hkd": {
    "3m": {
      "new_funds": {
        "rate": 3.0,
        "min_deposit": 1000000,
        "note": "...",
        "source": "bank",
        "conditions": []
      },
      "existing_funds": {
        "rate": null,
        "min_deposit": null,
        "note": null,
        "source": null
      },
      "exchange": {
        "rate": null,
        "min_deposit": null,
        "note": null,
        "source": null,
        "conditions": ["exchange"]
      }
    }
  }
}
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
RATES_FILE = os.path.join(DATA_DIR, 'rates.json')

ALL_CURRENCIES = ['hkd', 'usd', 'cny']
ALL_PERIODS = ['1w', '1m', '2m', '3m', '4m', '6m', '9m', '12m']


def migrate_entry(entry):
    """Convert a single period entry from old to new structure."""
    if not isinstance(entry, dict):
        # Bare value (old format)
        return {
            'new_funds': {'rate': None, 'min_deposit': None, 'note': None, 'source': None},
            'existing_funds': {'rate': entry, 'min_deposit': None, 'note': None, 'source': None},
            'exchange': {'rate': None, 'min_deposit': None, 'note': None, 'source': None, 'conditions': ['exchange']},
        }
    
    # Check if already new structure
    if 'new_funds' in entry or 'existing_funds' in entry or 'exchange' in entry:
        return entry
    
    # Old structure - need to migrate
    rate = entry.get('rate')
    fund_type = entry.get('fund_type')
    conditions = entry.get('conditions', [])
    min_deposit = entry.get('min_deposit')
    note = entry.get('note')
    source = entry.get('source')
    
    # Determine target slot based on fund_type and conditions
    if 'exchange' in conditions:
        target_slot = 'exchange'
    elif fund_type == 'new_funds':
        target_slot = 'new_funds'
    elif fund_type == 'existing_funds':
        target_slot = 'existing_funds'
    elif fund_type is None:
        # General rate - put in existing_funds
        target_slot = 'existing_funds'
    else:
        target_slot = 'existing_funds'
    
    # Build new structure
    new_entry = {
        'new_funds': {'rate': None, 'min_deposit': None, 'note': None, 'source': None, 'conditions': []},
        'existing_funds': {'rate': None, 'min_deposit': None, 'note': None, 'source': None, 'conditions': []},
        'exchange': {'rate': None, 'min_deposit': None, 'note': None, 'source': None, 'conditions': ['exchange']},
    }
    
    # Put the rate in the appropriate slot
    new_entry[target_slot] = {
        'rate': rate,
        'min_deposit': min_deposit,
        'note': note,
        'source': source,
        'conditions': conditions,
    }
    
    return new_entry


def migrate_bank(bank):
    """Migrate a bank's rate data to new structure."""
    for cur in ALL_CURRENCIES:
        if cur not in bank:
            bank[cur] = {}
        
        for period in ALL_PERIODS:
            if period not in bank[cur]:
                # Initialize empty entry
                bank[cur][period] = {
                    'new_funds': {'rate': None, 'min_deposit': None, 'note': None, 'source': None},
                    'existing_funds': {'rate': None, 'min_deposit': None, 'note': None, 'source': None},
                    'exchange': {'rate': None, 'min_deposit': None, 'note': None, 'source': None, 'conditions': ['exchange']},
                }
            else:
                bank[cur][period] = migrate_entry(bank[cur][period])


def migrate_rates_file():
    """Migrate the entire rates.json file."""
    print("=" * 60)
    print("Rates.json Data Structure Migration")
    print("=" * 60)
    
    # Load current file
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data['banks'])} banks")
    
    # Backup
    backup_file = RATES_FILE + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Backup saved: {backup_file}")
    
    # Migrate each bank
    for bank in data['banks']:
        migrate_bank(bank)
        print(f"  ✓ {bank['name']}")
    
    # Add structure version marker
    data['structure_version'] = '2.0'
    data['structure_description'] = 'Separate rates per fund type (new_funds, existing_funds, exchange)'
    
    # Save
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Migration complete!")
    print(f"   New structure: rates.json")
    print(f"   Backup: {backup_file}")
    
    # Verify
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)
    
    with open(RATES_FILE, 'r', encoding='utf-8') as f:
        verified = json.load(f)
    
    sample_bank = verified['banks'][0]
    sample_period = sample_bank['hkd']['3m']
    
    print(f"Sample entry ({sample_bank['name']} HKD 3m):")
    print(json.dumps(sample_period, indent=2, ensure_ascii=False))
    
    if 'new_funds' in sample_period:
        print("\n✅ Structure looks correct!")
    else:
        print("\n❌ Migration may have failed")


if __name__ == '__main__':
    migrate_rates_file()