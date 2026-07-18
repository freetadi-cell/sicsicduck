from firebase_admin import credentials, db, messaging
import firebase_admin

cred = credentials.Certificate('data/fcm-service-account.json')
firebase_admin.initialize_app(cred, {'databaseURL': 'https://sicsicduck-default-rtdb.firebaseio.com'})

ref = db.reference('fcmTokens')
tokens_data = ref.get() or {}

print('檢查並清理失效 tokens...')
valid_tokens = []

for key, value in tokens_data.items():
    if isinstance(value, dict) and 'token' in value:
        token = value['token']
        # 測試 token 是否有效
        try:
            msg = messaging.Message(
                notification=messaging.Notification(title='Test', body='Test'),
                token=token
            )
            messaging.send(msg, dry_run=True)
            valid_tokens.append((key, token))
            print(f'✅ Token valid: {token[:20]}...')
        except Exception as e:
            error_str = str(e)
            if 'NotRegistered' in error_str or 'Unregistered' in error_str or 'unregistered' in error_str.lower():
                ref.child(key).delete()
                print(f'❌ Removed invalid: {token[:20]}...')
            else:
                valid_tokens.append((key, token))
                print(f'⚠️ Keep token: {token[:20]}... (error: {e})')

print(f'\n有效 tokens: {len(valid_tokens)}')

# 發送通知到有效 tokens
sent_count = 0
if valid_tokens:
    for key, token in valid_tokens:
        try:
            msg = messaging.Message(
                notification=messaging.Notification(
                    title='食息鴨測試通知 🔔',
                    body='這是測試通知，請確認是否收到'
                ),
                data={
                    'title': '食息鴨測試通知 🔔',
                    'body': '這是測試通知，請確認是否收到',
                    'url': 'https://sicsicduck.com'
                },
                token=token
            )
            r = messaging.send(msg)
            print(f'📤 Sent to {token[:20]}...: {r}')
            sent_count += 1
        except Exception as e:
            print(f'❌ Failed to send to {token[:20]}...: {e}')
            # 如果發送失敗係因為 token 失效，刪除佢
            if 'Unregistered' in str(e) or 'NotRegistered' in str(e):
                ref.child(key).delete()
                print(f'🗑️ Deleted invalid token from database')

print(f'\n✅ 成功發送 {sent_count} 個通知')
