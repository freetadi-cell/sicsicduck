#!/bin/bash
# Auto-fetch news from NewsData.io
# Runs every 8 hours via cron

cd /home/freet/.openclaw/workspace/sicsicduck

# Fetch latest news
python3 scripts/fetch_news.py

# Check if there are changes
if git diff --quiet data/news.json news.html; then
    echo "No changes to commit"
else
    # Commit and push changes
    git add data/news.json news.html
    git commit -m "Auto-update news $(date '+%Y-%m-%d %H:%M')"
    git push
    echo "News updated and pushed to GitHub"
fi
