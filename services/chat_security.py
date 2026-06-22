"""Chat security helpers — validation, moderation checks, upload safety."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

PROHIBITED_URL_RE = re.compile(r'(https?://|www\.)\S+', re.IGNORECASE)
PROHIBITED_EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PROHIBITED_PHONE_RE = re.compile(r'\d[\d\s-]{6,}\d')

PUBLIC_CHAT_ROOMS = frozenset({
    'general', 'dating', 'strangers', 'beginners', 'trade', 'vip',
})

ATTACHMENT_RE = re.compile(
    r'^\[\[(image|video|file):(uploads/chat/chat_\d+_[a-f0-9]+\.(?:png|jpe?g|gif|webp|mp4|pdf|txt))(?:\|([^\]]+))?\]\]$',
    re.IGNORECASE,
)

ALLOWED_UPLOAD_EXT = {
    'png': 'image', 'jpg': 'image', 'jpeg': 'image',
    'gif': 'image', 'webp': 'image', 'mp4': 'video',
    'pdf': 'file', 'txt': 'file',
}

MAX_CHAT_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_ASSISTANT_MESSAGE_LEN = 800
ONLINE_WINDOW_MINUTES = 5


def contains_prohibited_content(text: str) -> bool:
    """Block URLs, emails, and phone numbers in player chat."""
    if not text:
        return False
    if PROHIBITED_URL_RE.search(text):
        return True
    if PROHIBITED_EMAIL_RE.search(text):
        return True
    if PROHIBITED_PHONE_RE.search(text):
        return True
    return False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def chat_send_block_reason(user, now: Optional[datetime] = None) -> Optional[str]:
    """Return a stable reason code if the user may not send chat messages."""
    if user is None:
        return 'not_authenticated'
    if getattr(user, 'is_chat_banned', False):
        return 'banned'
    until = getattr(user, 'chat_muted_until', None)
    if until:
        now_utc = _utc_now()
        now_naive = now_utc.replace(tzinfo=None) if now is None else _as_utc_naive(now)
        until_naive = _as_utc_naive(until)
        if until_naive > now_naive:
            return 'muted'
    return None


def user_is_online(user, minutes: int = ONLINE_WINDOW_MINUTES) -> bool:
    last_seen = getattr(user, 'last_seen', None) if user else None
    if not last_seen:
        return False
    now = _utc_now()
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now - last_seen).total_seconds() < max(1, minutes) * 60


def normalize_room(room: str) -> str:
    r = (room or 'general').strip().lower()
    return r if r in PUBLIC_CHAT_ROOMS else 'general'


def moderator_can_act(actor, target) -> bool:
    if not actor or not target:
        return False
    try:
        from models.user import UserRole
        if actor.role.value < UserRole.MODERATOR.value:
            return False
        if target.role.value >= actor.role.value:
            return False
        return True
    except Exception:
        return False


def is_safe_chat_upload_rel_path(path: str) -> bool:
    p = (path or '').replace('\\', '/').lstrip('/')
    if '..' in p or not p.startswith('uploads/chat/'):
        return False
    return bool(re.match(
        r'^uploads/chat/chat_\d+_[a-f0-9]+\.(png|jpe?g|gif|webp|mp4|pdf|txt)$',
        p, re.IGNORECASE))


def validate_message_attachments(message: str) -> bool:
    """Only allow attachment tokens with safe paths."""
    raw = message or ''
    if '[[' not in raw:
        return True
    if not raw.strip().startswith('[['):
        return False
    return bool(ATTACHMENT_RE.match(raw.strip()))


def validate_upload_magic(save_path: str, kind: str) -> bool:
    try:
        if kind == 'image':
            import imghdr
            detected = imghdr.what(save_path)
            if detected in ('png', 'jpeg', 'gif'):
                return True
        if save_path.lower().endswith('.webp'):
            with open(save_path, 'rb') as fh:
                header = fh.read(16)
            return header.startswith(b'RIFF') and b'WEBP' in header
            return False
        if kind == 'video':
            with open(save_path, 'rb') as fh:
                head = fh.read(12)
            return len(head) >= 8 and head[4:8] == b'ftyp'
        if kind == 'pdf':
            with open(save_path, 'rb') as fh:
                return fh.read(5) == b'%PDF-'
        if kind == 'file' and save_path.lower().endswith('.txt'):
            with open(save_path, 'rb') as fh:
                chunk = fh.read(4096)
            try:
                chunk.decode('utf-8')
                return True
            except UnicodeDecodeError:
                return False
    except Exception:
        return False
    return False


def scan_upload_file(
    filename: str, stream, max_bytes: int = MAX_CHAT_UPLOAD_BYTES,
) -> Tuple[Optional[str], Optional[str], int]:
    """Returns (kind, ext, size) or (None, error_key, 0)."""
    ext = ''
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    kind = ALLOWED_UPLOAD_EXT.get(ext)
    if not kind:
        return None, 'unsupported_type', 0
    try:
        stream.seek(0, os.SEEK_END)
        size = int(stream.tell() or 0)
        stream.seek(0)
    except Exception:
        size = 0
    if size > max_bytes:
        return None, 'too_large', size
    return kind, ext, size
