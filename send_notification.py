#!/usr/bin/env python3
from firebase_admin import credentials, messaging, db
import firebase_admin
from pathlib import Path
import json

cred = credentials.Certificate(Path(__file__).parent / 'data' / 'fcm-service-account.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://sicsicduck-default-rtdb.firebaseio.com'})

# Get tokens
ref = db.reference('fcmTokens')
tokens = [v['token'] for v in (ref.get() or {}).values() if isinstance(v, dict) and 'token' in v]

print(f'Found {len(tokens)} subscribers')

# Get top rates
with open(Path(__file__).parent / 'data' / 'rates.json') as f:
    data = json.load(f)

best = {}
for bank in data.get('banks', []):
    hkd = bank.get('hkd', {})
    if not isinstance(hkd, dict): continue
    for m in ['3m', '6m', '12m']:
        r = hkd.get(m)
        if r and isinstance(r, (int, float)):
            if m not in best or r > best[m]['rate']:
                best[m] = {'bank': bank['name'], 'rate': r}

body = '查看今日最新定期存款利率'
if best:
    parts = [f"{m}: {best[m]['bank']} {best[m]['rate']:.2f}%" for m in ['3m', '6m', '12m'] if m in best]
    body = ' | '.join(parts)

title = '食息鴨每日利率更新 💰'
print(f'Title: {title}')
print(f'Body: {body}')

# Send
for token in tokens:
    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=***
    )
    try:
        r = messaging.send(msg)
        print(f'✅ Sent: {r}')
    except Exception as e:
        print(f'❌ Error: {e}')