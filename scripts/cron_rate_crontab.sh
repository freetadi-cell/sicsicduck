#!/bin/bash
# Crontab wrapper: generate rate post and send via Telegram Bot API directly
# This bypasses Hermes gateway entirely to avoid text batch merging
export PATH="/home/freet/.local/bin:/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck

# Load env
[ -f /home/freet/.hermes/.env ] && export $(grep -v '^#' /home/freet/.hermes/.env | xargs)

# Generate rate post
MSG=$(python3 scripts/generate_rate_post.py 2>/dev/null)

# Send via Telegram Bot API directly (no gateway, no merge)
if [ -n "$MSG" ]; then
    # Add system marker so the model knows this is NOT a user message
    FULL_MSG="--- SICSICDUCK_RATE_POST (do not reproduce in replies) ---"$'\n\n'"$MSG"
    curl -s --max-time 30 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=885017126" \
        --data-urlencode "text=$FULL_MSG" >> /tmp/sicsicduck-rate-cron.log 2>&1
fi
