#!/bin/bash
# Daily FCM Push Notification Trigger
# This script is called by OpenClaw cron job

cd /home/freet/.openclaw/workspace/hk_deposit_rates
python3 send_push_notification.py
