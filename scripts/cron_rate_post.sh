#!/bin/bash
export PATH="/home/freet/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /home/freet/.openclaw/workspace/sicsicduck
python3 scripts/generate_rate_post.py >> /tmp/sicsicduck-rate-post.log 2>&1
