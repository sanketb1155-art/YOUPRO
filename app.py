from flask import Flask, request, jsonify, g
import random
import time
import logging
from functools import wraps
from collections import OrderedDict

app = Flask(__name__)

# ==================== CONFIG ====================
PIPED_PROXIES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
    "https://pipedapi.rivo.lol",
]

# Simple in-memory cache with TTL
cache = OrderedDict()
MAX_CACHE_SIZE = 200
CACHE_TTL = 600  # 10 minutes

# Rate limiting
rate_limit_store = {}
RATE_LIMIT = 30  # requests per minute

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stats
stats = {'requests': 0, 'cache_hits': 0, 'errors': 0, 'start_time': time.time()}

# ==================== CACHE ====================
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

# ==================== RATE LIMITER ====================
def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = request.remote_addr
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

# ==================== ROUTES ====================
@app.route('/')
def home():
    return jsonify({
        'name': 'YouPro API Pro',
        'version': '10.0',
        'endpoints': ['/api/status', '/api/trending', '/api/video/search', '/api/video/info', '/api/video/formats', '/api/video/related', '/api/download']
    })

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'online',
        'uptime': int(time.time() - stats['start_time']),
        'requests': stats['requests'],
        'cache_hits': stats['cache_hits'],
        'errors': stats['errors'],
        'proxies_alive': len(PIPED_PROXIES)
    })

# ==================== TRENDING ====================
@app.route('/api/trending')
@rate_limit
def trending():
    stats['requests'] += 1
    region = request.args.get('region', 'IN')
    cache_key = f"trending_{region}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist', 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/feed/trending?gl={region}", download=False)
            videos = []
            for e in info.get('entries', [])[:30]:
                if e:
                    videos.append({
                        'id': e['id'], 'title': e.get('title',''), 'channel': e.get('uploader',''),
                        'duration': e.get('duration',0), 'views': e.get('view_count',0),
                        'thumbnail': (e.get('thumbnails',[{}])[-1].get('url',''))
                    })
            result = {'success': True, 'videos': videos, 'count': len(videos)}
            set_cache(cache_key, result, 1800)
            return jsonify(result)
    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Trending error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== SEARCH ====================
@app.route('/api/video/search')
@rate_limit
def search():
    stats['requests'] += 1
    query = request.args.get('q', 'trending')
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 30)), 100)
    
    cache_key = f"search_{query}_{page}_{per_page}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist', 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{per_page*page}:{query}", download=False)
            all_v = []
            for e in info.get('entries', []):
                if e:
                    all_v.append({
                        'id': e['id'], 'title': e.get('title',''), 'channel': e.get('uploader',''),
                        'duration': e.get('duration',0), 'thumbnail': (e.get('thumbnails',[{}])[-1].get('url',''))
                    })
            s = (page-1)*per_page
            result = {'success': True, 'videos': all_v[s:s+per_page], 'has_next': len(all_v) > s+per_page}
            set_cache(cache_key, result, 600)
            return jsonify(result)
    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Search error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== VIDEO INFO ====================
@app.route('/api/video/info')
@rate_limit
def video_info():
    stats['requests'] += 1
    video_id = request.args.get('id', '')
    if not video_id: return jsonify({'success': False, 'error': 'Missing ID'})

    cache_key = f"info_{video_id}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
            result = {
                'success': True,
                'title': info.get('title',''),
                'channel': info.get('uploader',''),
                'duration': info.get('duration',0),
                'views': info.get('view_count',0),
                'likes': info.get('like_count',0),
                'thumbnail': info.get('thumbnail',''),
                'description': (info.get('description','') or '')[:300]
            }
            set_cache(cache_key, result, 3600)
            return jsonify(result)
    except Exception as e:
        stats['errors'] += 1
        return jsonify({'success': False, 'error': str(e)})

# ==================== FORMATS ====================
@app.route('/api/video/formats')
@rate_limit
def formats():
    stats['requests'] += 1
    video_id = request.args.get('id', '')
    quality = request.args.get('quality', '720p')
    if not video_id: return jsonify({'success': False})

    cache_key = f"formats_{video_id}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    proxies = list(PIPED_PROXIES)
    random.shuffle(proxies)

    for proxy in proxies:
        try:
            import requests as r
            resp = r.get(f"{proxy}/streams/{video_id}", timeout=10, headers={'User-Agent': 'YouPro/10.0'})
            if resp.status_code != 200: continue
            data = resp.json()
            fmts = []
            for s in data.get('videoStreams', []):
                url = s.get('url', '')
                if url:
                    fmts.append({'url': url, 'quality': s.get('quality',''), 'height': s.get('height',720)})
            if fmts:
                result = {'success': True, 'title': data.get('title',''), 'formats': fmts, 'proxy': proxy}
                set_cache(cache_key, result, 300)
                return jsonify(result)
        except Exception as e:
            logger.warning(f"Proxy {proxy} failed: {e}")
            continue

    stats['errors'] += 1
    return jsonify({'success': False, 'error': 'All proxies failed'})

# ==================== RELATED ====================
@app.route('/api/video/related')
@rate_limit
def related():
    stats['requests'] += 1
    video_id = request.args.get('id', '')
    if not video_id: return jsonify({'success': False})

    cache_key = f"related_{video_id}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    for proxy in random.sample(PIPED_PROXIES, 3):
        try:
            import requests as r
            resp = r.get(f"{proxy}/streams/{video_id}", timeout=10)
            if resp.status_code != 200: continue
            data = resp.json()
            related_vids = data.get('relatedStreams', [])[:15]
            result = {'success': True, 'videos': [{'id': v.get('url','').split('=')[-1], 'title': v.get('title',''), 'channel': v.get('uploaderName',''), 'thumbnail': v.get('thumbnail','')} for v in related_vids]}
            set_cache(cache_key, result, 1800)
            return jsonify(result)
        except: continue

    return jsonify({'success': False, 'error': 'Failed'})

# ==================== DOWNLOAD ====================
@app.route('/api/download')
@rate_limit
def download():
    stats['requests'] += 1
    video_id = request.args.get('id', '')
    quality = request.args.get('quality', 'best')
    if not video_id: return jsonify({'success': False})

    for proxy in random.sample(PIPED_PROXIES, 3):
        try:
            import requests as r
            resp = r.get(f"{proxy}/streams/{video_id}", timeout=10)
            if resp.status_code != 200: continue
            data = resp.json()
            for s in data.get('videoStreams', []):
                if s.get('quality','') == quality or quality == 'best':
                    return jsonify({'success': True, 'download_url': s.get('url',''), 'title': data.get('title',''), 'quality': s.get('quality','')})
        except: continue

    return jsonify({'success': False, 'error': 'No download link found'})

# ==================== PROXY HEALTH ====================
@app.route('/api/proxy/health')
def proxy_health():
    results = {}
    for proxy in PIPED_PROXIES:
        try:
            import requests as r
            resp = r.get(f"{proxy}/streams/dQw4w9WgXcQ", timeout=5)
            results[proxy] = 'alive' if resp.status_code == 200 else f'status_{resp.status_code}'
        except:
            results[proxy] = 'dead'
    return jsonify({'success': True, 'proxies': results})

# ==================== GZIP COMPRESSION ====================
@app.after_request
def add_header(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if request.headers.get('Accept-Encoding', '').find('gzip') >= 0:
        response.headers['Content-Encoding'] = 'gzip'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
