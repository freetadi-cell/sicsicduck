#!/usr/bin/env python3
"""
FCM Push Notification Sender for 食息鴨
Sends daily deposit rate updates to all subscribers
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, messaging, db

# Config
SERVICE_ACCOUNT_PATH = Path(__file__).parent / 'data' / 'fcm-service-account.json'
RATES_JSON_PATH = Path(__file__).parent / 'data' / 'rates.json'

def init_firebase():
    """Initialize Firebase Admin SDK"""
    if firebase_admin._apps:
        return
    
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://sicsicduck-default-rtdb.firebaseio.com'
    })

def get_all_tokens():
    """Get all FCM tokens from Firebase Realtime Database"""
    try:
        ref = db.reference('fcmTokens')
        tokens_data = ref.get()
        
        if not tokens_data:
            print("No tokens found")
            return []
        
        tokens = []
        for key, value in tokens_data.items():
            if isinstance(value, dict) and 'token' in value:
                tokens.append(value['token'])
        
        print(f"Found {len(tokens)} subscribers")
        return tokens
    except Exception as e:
        print(f"Error getting tokens: {e}")
        return []

def get_top_rates():
    """Get top deposit rates from rates.json"""
    try:
        with open(RATES_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get HKD rates
        hkd_rates = data.get('banks', [])
        
        # Find best 3-month rate
        best_3m = None
        best_6m = None
        best_12m = None
        
        for bank in hkd_rates:
            bank_name = bank.get('name', '')
            hkd = bank.get('hkd', {})
            
            # 3 month
            rate_3m = hkd.get('3m')
            if rate_3m and (not best_3m or rate_3m > best_3m['rate']):
                best_3m = {'bank': bank_name, 'rate': rate_3m}
            
            # 6 month
            rate_6m = hkd.get('6m')
            if rate_6m and (not best_6m or rate_6m > best_6m['rate']):
                best_6m = {'bank': bank_name, 'rate': rate_6m}
            
            # 12 month
            rate_12m = hkd.get('12m')
            if rate_12m and (not best_12m or rate_12m > best_12m['rate']):
                best_12m = {'bank': bank_name, 'rate': rate_12m}
        
        return {
            '3m': best_3m,
            '6m': best_6m,
            '12m': best_12m
        }
    except Exception as e:
        print(f"Error reading rates: {e}")
        return None

def format_notification_message(rates):
    """Format notification message with top rates"""
    if not rates:
        return "食息鴨每日利率更新 💰", "查看今日最新定期存款利率"
    
    lines = []
    if rates.get('3m'):
        lines.append(f"3個月: {rates['3m']['bank']} {rates['3m']['rate']:.2f}%")
    if rates.get('6m'):
        lines.append(f"6個月: {rates['6m']['bank']} {rates['6m']['rate']:.2f}%")
    if rates.get('12m'):
        lines.append(f"12個月: {rates['12m']['bank']} {rates['12m']['rate']:.2f}%")
    
    title = "食息鴨每日利率更新 💰"
    body = " | ".join(lines) if lines else "查看今日最新定期存款利率"
    
    return title, body

def send_push_notification(title, body, tokens):
    """Send push notification to all tokens"""
    if not tokens:
        print("No tokens to send to")
        return False
    
    # Send in batches of 500 (FCM limit)
    success_count = 0
    failure_count = 0
    
    for i in range(0, len(tokens), 500):
        batch = tokens[i:i+500]
        
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            tokens=batch,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon='/favicon.ico',
                    badge='/favicon.ico',
                    tag='sicsicduck-rate-update'
                )
            )
        )
        
        try:
            response = messaging.send_multicast(message)
            success_count += response.success_count
            failure_count += response.failure_count
            print(f"Batch {i//500 + 1}: {response.success_count} success, {response.failure_count} failed")
        except Exception as e:
            print(f"Error sending batch: {e}")
            failure_count += len(batch)
    
    print(f"Total: {success_count} success, {failure_count} failed")
    return success_count > 0

def main():
    """Main function"""
    print(f"=== FCM Push Notification - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    # Initialize Firebase
    init_firebase()
    
    # Get all tokens
    tokens = get_all_tokens()
    if not tokens:
        print("No subscribers, exiting")
        return
    
    # Get top rates
    rates = get_top_rates()
    
    # Format message
    title, body = format_notification_message(rates)
    print(f"Title: {title}")
    print(f"Body: {body}")
    
    # Send notification
    send_push_notification(title, body, tokens)
    
    print("=== Done ===")

if __name__ == '__main__':
    main()
