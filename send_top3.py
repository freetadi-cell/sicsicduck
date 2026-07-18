#!/usr/bin/env python3
import json
from firebase_admin import credentials, db, messaging
import firebase_admin

# Load rates
with open('data/rates.json') as f:
    data = json.load(f)

# Extract all HKD rates for 3m, 6m, 12m
rates_list = {'3m': [], '6m': [], '12m': []}

for bank in data.get('banks', []):
    name = bank['name']
    hkd = bank.get('hkd', {})
    if not isinstance(hkd, dict): continue
    
    for period in ['3m', '6m', '12m']:
        period_data = hkd.get(period)
        if isinstance(period_data, dict):
            # Check new_funds first
            new_funds = period_data.get('new_funds', {})
            if isinstance(new_funds, dict) and new_funds.get('rate'):
                rates_list[period].append({'bank': name, 'rate': new_funds['rate']})
            # Check direct rate
            elif period_data.get('rate'):
                rates_list[period].append({'bank': name, 'rate': period_data['rate']})
        elif isinstance(period_data, (int, float)):
            rates_list[period].append({'bank': name, 'rate': period_data})

# Sort and get top 3
for period in ['3m', '6m', '12m']:
    rates_list[period].sort(key=lambda x: x['rate'], reverse=True)
    rates_list[period] = rates_list[period][:3]

# Build notification
lines = []
for period in ['3m', '6m', '12m']:
    lines.append(f'【{period}】')
    for i, r in enumerate(rates_list[period], 1):
        lines.append(f'{i}. {r["bank"]} {r["rate"]:.2f}%')

body = '\n'.join(lines)

print('推送內容：')
print(body)
print()

# Send FCM
cred = credentials.Certificate('data/fcm-service-account.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://sicsicduck-default-rtdb.firebaseio.com'})

ref = db.reference('fcmTokens')
tokens_data = ref.get() or {}

for key, val in tokens_data.items():
    if isinstance(val, dict) and 'token' in val:
        token = val['token']
        msg = messaging.Message(
            notification=messaging.Notification(
                title='港元定期 Top 3 💰',
                body=body
            ),
            data={
                'title': '港元定期 Top 3 💰',
                'body': body,
                'url': 'https://sicsicduck.com'
            },
            token=***
        )
        r = messaging.send(msg)
        print(f'✅ 已發送: {r}')