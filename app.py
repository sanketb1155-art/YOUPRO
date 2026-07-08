from flask import Flask, request, jsonify
import random
import time
import logging
from functools import wraps
from collections import OrderedDict
import yt_dlp
import requests

app = Flask(__name__)

# ==================== CONFIG ====================
PIPED_PROXIES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
    "https://pipedapi.rivo.lol",
]

cache = OrderedDict()
MAX_CACHE_SIZE = 200
CACHE_TTL = 600

rate_limit_store = {}
RATE_LIMIT = 40

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

stats = {'requests': 0, 'cache_hits': 0, 'errors': 0, 'start_time': time.time()}

# ==================== CACHE & RATE LIMIT ====================
def get_cache(key):
    if key in cache:
        value, expiry = cache[key]
        if time.time() < expiry:
            stats['cache_hits'] += 1
            cache.move_to_end(key)
            return value
        del cache[key]
    return None

def set_cache(key, value, ttl=CACHE_TTL):
    if len(cache) >= MAX_CACHE_SIZE:
        cache.popitem(last=False)
    cache[key] = (value, time.time() + ttl)

def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = request.remote_addr or 'unknown'
        now = time.time()
        if client_ip in rate_limit_store:
            requests_made = [t for t in rate_limit_store[client_ip] if now - t < 60]
            if len(requests_made) >= RATE_LIMIT:
                return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
            rate_limit_store[client_ip] = requests_made
        else:
            rate_limit_store[client_ip] = []
        rate_limit_store[client_ip].append(now)
        return f(*args, **kwargs)
    return decorated

# ==================== MAIN FORMATS ENDPOINT (Best Version) ====================
@app.route('/api/video/formats')
@rate_limit
def formats():
    stats['requests'] += 1
    video_id = request.args.get('id', '').strip()
    if not video_id:
        return jsonify({'success': False, 'error': 'Missing video ID'})

    cache_key = f"formats_{video_id}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    result = None

    # === Layer 1: yt_dlp (Most Reliable) ===
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_retries': 3,
            'socket_timeout': 12,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            formats_list = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('url') and f.get('height', 0) >= 144:
                    formats_list.append({
                        'url': f['url'],
                        'quality': f"{f.get('height')}p",
                        'height': f.get('height'),
                    })
            
            if formats_list:
                formats_list = sorted(formats_list, key=lambda x: x['height'], reverse=True)
                result = {
                    'success': True,
                    'title': info.get('title', 'Video'),
                    'formats': formats_list[:8],
                    'source': 'yt_dlp'
                }
                set_cache(cache_key, result)
                return jsonify(result)
    except Exception as e:
        logger.warning(f"yt_dlp failed: {e}")

    # === Layer 2: Piped Proxies Fallback ===
    proxies = list(PIPED_PROXIES)
    random.shuffle(proxies)
    
    for proxy in proxies:
        try:
            resp = requests.get(
                f"{proxy}/streams/{video_id}", 
                timeout=10,
                headers={'User-Agent': 'YouPro/10.0'}
            )
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            fmts = []
            for s in data.get('videoStreams', []):
                if s.get('url'):
                    fmts.append({
                        'url': s['url'],
                        'quality': s.get('quality', '720p'),
                        'height': s.get('height', 720)
                    })
            
            if fmts:
                fmts = sorted(fmts, key=lambda x: x['height'], reverse=True)
                result = {
                    'success': True,
                    'title': data.get('title', 'Video'),
                    'formats': fmts,
                    'source': 'piped'
                }
                set_cache(cache_key, result, 300)
                return jsonify(result)
        except Exception as e:
            logger.warning(f"Proxy {proxy} failed: {str(e)[:100]}")
            continue

    # === Final Failure ===
    stats['errors'] += 1
    error_result = {'success': False, 'error': 'All extraction methods failed. Try again later.'}
    set_cache(cache_key, error_result, 60)
    return jsonify(error_result)


# Other routes (status, trending, etc.) same rakh sakte ho...

@app.route('/')
def home():
    return jsonify({'status': 'online', 'message': 'YouPro Backend - Multi Layer Extraction Active'})

@app.route('/api/proxy/health')
def proxy_health():
    results = {}
    for proxy in PIPED_PROXIES:
        try:
            resp = requests.get(f"{proxy}/streams/dQw4w9WgXcQ", timeout=6)
            results[proxy] = 'alive' if resp.status_code == 200 else f'error_{resp.status_code}'
        except:
            results[proxy] = 'dead'
    return jsonify({'success': True, 'proxies': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
