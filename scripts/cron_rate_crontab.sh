#!/bin/bash
# crontab wrapper: generate rate post and send via hermes
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck

# Generate rate post to temp file
TMPFILE=$(mktemp /tmp/rate-post-XXXXXX.txt)
python3 scripts/generate_rate_post.py > "$TMPFILE" 2>/dev/null

# Send via hermes
if [ -s "$TMPFILE" ]; then
    MSG=$(cat "$TMPFILE")
    hermes send -t telegram "$MSG" >> /tmp/sicsicduck-rate-cron.log 2>&1
fi

rm -f "$TMPFILE"
