#!/usr/bin/env python3
from firebase_admin import credentials, db, messaging
import firebase_admin

cred = credentials.Certificate('data/fcm-service-account.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://sicsicduck-default-rtdb.firebaseio.com'})

ref = db.reference('fcmTokens')
tokens_data = ref.get() or {}

for key, val in tokens_data.items():
    if isinstance(val, dict) and 'token' in val:
        token = val['token']
        msg = messaging.Message(
            notification=messaging.Notification(title='Test', body='test'),
            token=token
        )
        r = messaging.send(msg)
        print(f'✅ 已發送: {r}')