from flask import Blueprint, jsonify, request
try:
    from youtubesearchpython import VideosSearch
except ImportError:
    VideosSearch = None
try:
    import httpx
    from packaging.version import Version
except Exception:
    httpx = None
from flask_babel import gettext as _
import logging

bp = Blueprint('youtube', __name__, url_prefix='/api/youtube')


@bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []})
    if VideosSearch is None:
        return jsonify({'error': _('خدمة البحث غير متاحة حالياً')}), 503
    if httpx and Version(getattr(httpx, "__version__", "0")) >= Version(
        "0.28.0"
    ):
        logging.error("httpx version incompatible: %s", httpx.__version__)
        return jsonify({'error': _('خدمة البحث غير متاحة حالياً')}), 503

    try:
        # Search for videos (limit 10)
        videos_search = VideosSearch(
            query,
            limit=10,
            language='ar',
            region='SA',
        )
        results = videos_search.result()

        videos = []
        if 'result' in results:
            for item in results['result']:
                # Extract relevant info
                try:
                    video_id = item['id']
                    title = item['title']
                    thumbnails = item.get('thumbnails') or []
                    thumbnail = thumbnails[0].get('url') if thumbnails else ''
                    duration = item.get('duration')
                    channel = (
                        item['channel']['name']
                        if item.get('channel')
                        else ''
                    )

                    videos.append({
                        'id': video_id,
                        'title': title,
                        'thumbnail': thumbnail,
                        'duration': duration,
                        'channel': channel
                    })
                except Exception:
                    continue

        return jsonify({'results': videos})

    except Exception as exc:
        logging.error("YouTube search error: %s", exc)
        return jsonify({'error': _('حدث خطأ أثناء البحث')}), 500
