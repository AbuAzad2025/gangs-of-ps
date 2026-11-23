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

# Patch the fragile youtubesearchpython component parser: some videos have no
# channel id, which crashes the whole search with "can only concatenate str
# (not NoneType)". Make channel link tolerant of a missing id.
try:
    from youtubesearchpython.handlers import componenthandler as _ch

    _orig_get_video_component = _ch.ComponentHandler._getVideoComponent

    def _safe_get_video_component(self, element, shelfTitle=None):
        try:
            return _orig_get_video_component(self, element, shelfTitle)
        except TypeError:
            # Fall back to a minimal component built defensively.
            video = element
            if isinstance(element, dict):
                video = (element.get('videoRenderer')
                         or element.get('video')
                         or element)
            if not isinstance(video, dict):
                video = {}
            def _g(paths):
                try:
                    return self._getValue(video, paths)
                except Exception:
                    return None
            comp = {
                'type': 'video',
                'id': _g(['videoId']),
                'title': _g(['title', 'runs', 0, 'text']),
                'publishedTime': _g(['publishedTimeText', 'simpleText']),
                'duration': _g(['lengthText', 'simpleText']),
                'viewCount': {
                    'text': _g(['viewCountText', 'simpleText']),
                    'short': _g(['shortViewCountText', 'simpleText']),
                },
                'thumbnails': _g(['thumbnail', 'thumbnails']),
                'richThumbnail': _g(['richThumbnail', 'movingThumbnailRenderer', 'movingThumbnailDetails', 'thumbnails', 0]),
                'descriptionSnippet': _g(['detailedMetadataSnippets', 0, 'snippetText', 'runs']),
                'channel': {
                    'name': _g(['ownerText', 'runs', 0, 'text']),
                    'id': _g(['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']),
                    'thumbnails': _g(['channelThumbnailSupportedRenderers', 'channelThumbnailWithLinkRenderer', 'thumbnail', 'thumbnails']),
                },
                'accessibility': {
                    'title': _g(['title', 'accessibility', 'accessibilityData', 'label']),
                    'duration': _g(['lengthText', 'accessibility', 'accessibilityData', 'label']),
                },
            }
            comp['link'] = 'https://www.youtube.com/watch?v=' + (comp['id'] or '')
            comp['channel']['link'] = 'https://www.youtube.com/channel/' + (comp['channel']['id'] or '')
            comp['shelfTitle'] = shelfTitle
            return comp

    _ch.ComponentHandler._getVideoComponent = _safe_get_video_component

    # Same null-safety for shelf components, which can also be None.
    _orig_shelf = _ch.ComponentHandler._getShelfComponent
    def _safe_get_shelf_component(self, element):
        try:
            result = _orig_shelf(self, element)
        except Exception:
            result = None
        if not isinstance(result, dict):
            result = {}
        if not result.get('elements'):
            result['elements'] = []
        if 'title' not in result:
            result['title'] = None
        return result
    _ch.ComponentHandler._getShelfComponent = _safe_get_shelf_component
except Exception:
    pass

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

    # Try the localized search first, then fall back to a neutral one if the
    # upstream parser still rejects the payload (some queries/regions fail).
    results = None
    for kwargs in (
        {'limit': 10, 'language': 'ar', 'region': 'SA'},
        {'limit': 10, 'language': 'en', 'region': 'US'},
        {'limit': 10},
    ):
        try:
            videos_search = VideosSearch(query, **kwargs)
            results = videos_search.result()
            break
        except Exception as exc:
            logging.warning("YouTube search attempt failed (%s): %s", kwargs, exc)
            results = None

    videos = []
    if results and 'result' in results:
        for item in results['result']:
            # Extract relevant info
            try:
                video_id = item.get('id') or ''
                title = item.get('title') or ''
                thumbnails = item.get('thumbnails') or []
                thumbnail = ''
                if thumbnails and isinstance(thumbnails[0], dict):
                    thumbnail = thumbnails[0].get('url') or ''
                duration = item.get('duration')
                channel = ''
                if isinstance(item.get('channel'), dict):
                    channel = item['channel'].get('name') or ''

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

    # If every search attempt failed, degrade gracefully instead of 500.
    logging.error("YouTube search failed for query %r", query)
    return jsonify({'results': []})
