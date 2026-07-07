from flask import Flask, request, jsonify
import yt_dlp
import json

app = Flask(__name__)

# Video cache
video_cache = {}

@app.route('/')
def home():
    return jsonify({
        'name': 'YouPro API',
        'version': '1.0.0',
        'endpoints': [
            '/api/status',
            '/api/video/info?id=VIDEO_ID',
            '/api/video/formats?id=VIDEO_ID',
            '/api/video/search?q=QUERY'
        ]
    })

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'online',
        'cached_videos': len(video_cache),
        'version': '1.0.0'
    })

@app.route('/api/video/info')
def video_info():
    video_id = request.args.get('id', '')
    if not video_id:
        return jsonify({'success': False, 'error': 'Missing video ID'})
    
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
            return jsonify({
                'success': True,
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', ''),
                'views': info.get('view_count', 0),
                'description': info.get('description', '')[:200]
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/formats')
def video_formats():
    video_id = request.args.get('id', '')
    if not video_id:
        return jsonify({'success': False, 'error': 'Missing video ID'})
    
    # Return cached result if available
    if video_id in video_cache:
        return jsonify(video_cache[video_id])
    
    try:
        formats = []
        ydl_opts = {
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
            
            for f in info.get('formats', []):
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                
                # Only include formats with video
                if vcodec != 'none':
                    formats.append({
                        'format_id': f.get('format_id', ''),
                        'url': f.get('url', ''),
                        'quality': f.get('format_note', ''),
                        'height': f.get('height', 0),
                        'width': f.get('width', 0),
                        'filesize': f.get('filesize', 0),
                        'ext': f.get('ext', 'mp4'),
                        'has_audio': acodec != 'none'
                    })
        
        # Sort by height (highest first)
        formats.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        result = {
            'success': True,
            'title': info.get('title', ''),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'formats': formats
        }
        
        # Cache for 30 minutes
        video_cache[video_id] = result
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/search')
def search():
    query = request.args.get('q', 'trending')
    page = request.args.get('page', 1)
    
    if not query:
        return jsonify({'success': False, 'error': 'Missing search query'})
    
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'no_warnings': True
        }
        
        max_results = 20
        search_query = f"ytsearch{max_results}:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            
            videos = []
            for entry in info.get('entries', []):
                if entry:
                    videos.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', ''),
                        'channel': entry.get('uploader', ''),
                        'duration': entry.get('duration', 0),
                        'views': entry.get('view_count', 0),
                        'thumbnail': entry.get('thumbnails', [{}])[-1].get('url', '') if entry.get('thumbnails') else ''
                    })
            
            return jsonify({
                'success': True,
                'query': query,
                'videos': videos,
                'count': len(videos)
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/trending')
def trending():
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info('https://www.youtube.com/feed/trending', download=False)
            
            videos = []
            for entry in info.get('entries', [])[:20]:
                if entry:
                    videos.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', ''),
                        'channel': entry.get('uploader', ''),
                        'duration': entry.get('duration', 0),
                        'views': entry.get('view_count', 0),
                        'thumbnail': entry.get('thumbnails', [{}])[-1].get('url', '') if entry.get('thumbnails') else ''
                    })
            
            return jsonify({
                'success': True,
                'videos': videos,
                'count': len(videos)
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)