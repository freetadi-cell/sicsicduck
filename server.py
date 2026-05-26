#!/usr/bin/env python3
"""
Lightweight API server for hk_deposit_rates.
- Tracks online visitors (unique IPs in last 30 min)
- Serves the static site
- CORS-enabled API for GitHub Pages
"""

import os
import time
import threading
from flask import Flask, jsonify, send_from_directory, request, make_response

app = Flask(__name__)

# In-memory IP tracking: {ip: last_seen_timestamp}
visitors = {}
VISITOR_TIMEOUT = 1800  # 30 minutes
lock = threading.Lock()

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    'https://freetadi-cell.github.io',
    'http://localhost:8080',
]


@app.after_request
def add_cors(response):
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS or origin.endswith('.github.io'):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET'
        response.headers['Access-Control-Max-Age'] = '86400'
    return response


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
