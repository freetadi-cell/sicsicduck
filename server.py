#!/usr/bin/env python3
"""
Lightweight API server for hk_deposit_rates.
- Tracks online visitors (unique IPs in last 30 min)
- Serves the static site
"""

import os
import time
import threading
from flask import Flask, jsonify, send_from_directory, request

app = Flask(__name__)

# In-memory IP tracking: {ip: last_seen_timestamp}
visitors = {}
VISITOR_TIMEOUT = 1800  # 30 minutes
lock = threading.Lock()

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route('/api/online')
def online_count():
    """Return number of unique IPs in last 30 minutes."""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    now = time.time()

    with lock:
        visitors[ip] = now
        # Prune expired entries
        expired = [k for k, v in visitors.items() if now - v > VISITOR_TIMEOUT]
        for k in expired:
            del visitors[k]
        count = len(visitors)

    return jsonify({'count': count})


@app.route('/<path:path>')
def static_file(path):
    return send_from_directory(STATIC_DIR, path)


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
