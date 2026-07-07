from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'name': 'YouPro API', 'version': '3.0'})

@app.route('/api/status')
def status():
    return jsonify({'status': 'online'})

@app.route('/api/video/search')
def search():
    query = request.args.get('q', 'trending')
    page = int(request.args.get('page', 1))
    per_page = 50
    
    try:
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist', 'skip_download': True}
        # Get enough results for pagination
        total_needed = per_page * page
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
                        'thumbnail': entry.get('thumbnails', [{}])[-1].get('url', '') if entry.get('thumbnails') else ''
                    })
            
            # Slice for current page
            start = (page - 1) * per_page
            end = start + per_page
            videos = all_videos[start:end]
            
            return jsonify({
                'success': True,
                'videos': videos,
                'count': len(videos),
                'page': page,
                'has_next': len(all_videos) > end
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/formats')
def video_formats():
    video_id = request.args.get('id', '')
    if not video_id:
        return jsonify({'success': False, 'error': 'Missing video ID'})
    
    try:
        formats = []
        # NO CACHE — always fetch fresh URLs
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
                        'filesize': f.get('filesize', 0),
                        'has_audio': f.get('acodec', 'none') != 'none'
                    })
        
        formats.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'title': info.get('title', ''),
            'thumbnail': info.get('thumbnail', ''),
            'formats': formats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
