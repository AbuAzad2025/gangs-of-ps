from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from youtubesearchpython import VideosSearch
from flask_babel import gettext as _
import logging

bp = Blueprint('youtube', __name__, url_prefix='/api/youtube')

@bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': _('يرجى إدخال كلمة البحث')}), 400

    try:
        # Search for videos (limit 10)
        videosSearch = VideosSearch(query, limit=10, language='ar', region='SA')
        results = videosSearch.result()

        videos = []
        if 'result' in results:
            for item in results['result']:
                # Extract relevant info
                try:
                    video_id = item['id']
                    title = item['title']
                    thumbnail = item['thumbnails'][0]['url'] if item.get('thumbnails') else ''
                    duration = item.get('duration')
                    channel = item['channel']['name'] if item.get('channel') else ''
                    
                    videos.append({
                        'id': video_id,
                        'title': title,
                        'thumbnail': thumbnail,
                        'duration': duration,
                        'channel': channel
                    })
                except Exception as e:
                    continue

        return jsonify({'results': videos})

    except Exception as e:
        logging.error(f"YouTube search error: {e}")
        return jsonify({'error': _('حدث خطأ أثناء البحث')}), 500
