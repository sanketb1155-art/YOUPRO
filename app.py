from flask import Flask, request, jsonify
import yt_dlp
import random
import time

app = Flask(__name__)

# Multiple proxy APIs — koi bhi use kar sakta hai
PROXY_API_LIST = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.rivo.lol",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.lunar.icu",
]

# Stats
stats = {
    'total_requests': 0,
    'cached_videos': 0,
    'active_proxy': None,
    'start_time': time.time()
}

@app.route('/')
def home():
    return jsonify({
        'name': 'YouPro API PRO',
        'version': '5.0',
        'endpoints': [
            '/api/status',
            '/api/video/search?q=QUERY&page=1&per_page=50&proxy=auto',
            '/api/video/formats?id=VIDEO_ID&proxy=auto',
            '/api/video/proxy/list',
            '/api/video/proxy/switch'
        ]
    })

@app.route('/api/status')
def status():
    uptime = int(time.time() - stats['start_time'])
    return jsonify({
        'status': 'online',
        'uptime_seconds': uptime,
        'total_requests': stats['total_requests'],
        'active_proxy': stats['active_proxy'],
        'version': '5.0'
    })

@app.route('/api/video/search')
def search():
    stats['total_requests'] += 1
    query = request.args.get('q', 'trending')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    proxy_choice = request.args.get('proxy', 'auto')
    
    # Limit: max 200 per page, 50 pages = 10K videos
    per_page = min(per_page, 200)
    max_pages = 50
    
    try:
        results = {'success': False, 'videos': [], 'error': None}
        
        # Try multiple proxies
        proxies_to_try = get_proxy_list(proxy_choice)
        
        for proxy_url in proxies_to_try:
            try:
                stats['active_proxy'] = proxy_url
                
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': 'in_playlist',
                    'skip_download': True,
                    'no_warnings': True,
                }
                
                total_needed = min(per_page * page, per_page * max_pages)
                search_query = f"ytsearch{total_needed}:{query}"
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    all_videos = []
                    for entry in info.get('entries', []):
                        if entry:
                            all_videos.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', ''),
                                'channel': entry.get('uploader', ''),
                                'duration': entry.get('duration', 0),
                                'views': entry.get('view_count', 0),
                                'thumbnail': entry.get('thumbnails', [{}])[-1].get('url', '') if entry.get('thumbnails') else ''
                            })
                    
                    total_available = len(all_videos)
                    start = (page - 1) * per_page
                    end = min(start + per_page, total_available)
                    videos = all_videos[start:end]
                    
                    results = {
                        'success': True,
                        'videos': videos,
                        'count': len(videos),
                        'page': page,
                        'per_page': per_page,
                        'has_next': end < total_available and page < max_pages,
                        'total_available': total_available,
                        'proxy_used': proxy_url,
                        'max_pages': max_pages
                    }
                    break  # Success — stop trying more proxies
                    
            except Exception as e:
                continue  # Try next proxy
        
        if not results['success']:
            results['error'] = 'All proxies failed'
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/formats')
def video_formats():
    stats['total_requests'] += 1
    video_id = request.args.get('id', '')
    proxy_choice = request.args.get('proxy', 'auto')
    
    if not video_id:
        return jsonify({'success': False, 'error': 'Missing video ID'})
    
    try:
        formats = []
        proxies_to_try = get_proxy_list(proxy_choice)
        
        for proxy_url in proxies_to_try:
            try:
                stats['active_proxy'] = proxy_url
                
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                    
                    for f in info.get('formats', []):
                        vcodec = f.get('vcodec', 'none')
                        if vcodec != 'none':
                            formats.append({
                                'url': f.get('url', ''),
                                'quality': f.get('format_note', ''),
                                'height': f.get('height', 0),
                                'width': f.get('width', 0),
                                'filesize': f.get('filesize', 0),
                                'ext': f.get('ext', 'mp4'),
                                'fps': f.get('fps', 0),
                                'has_audio': f.get('acodec', 'none') != 'none',
                                'format_id': f.get('format_id', '')
                            })
                    
                    formats.sort(key=lambda x: x.get('height', 0), reverse=True)
                    
                    return jsonify({
                        'success': True,
                        'title': info.get('title', ''),
                        'thumbnail': info.get('thumbnail', ''),
                        'duration': info.get('duration', 0),
                        'formats': formats,
                        'proxy_used': proxy_url
                    })
                    
            except Exception as e:
                continue
        
        return jsonify({'success': False, 'error': 'All proxies failed for formats'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/proxy/list')
def proxy_list():
    return jsonify({
        'success': True,
        'proxies': PROXY_API_LIST,
        'active': stats['active_proxy'],
        'count': len(PROXY_API_LIST)
    })

@app.route('/api/video/proxy/switch')
def proxy_switch():
    new_proxy = random.choice(PROXY_API_LIST)
    stats['active_proxy'] = new_proxy
    return jsonify({'success': True, 'active_proxy': new_proxy})

def get_proxy_list(choice):
    if choice == 'auto':
        # Random order — load balancing
        proxies = list(PROXY_API_LIST)
        random.shuffle(proxies)
        return proxies
    elif choice == 'all':
        return list(PROXY_API_LIST)
    elif choice in PROXY_API_LIST:
        return [choice]
    else:
        return [random.choice(PROXY_API_LIST)]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
