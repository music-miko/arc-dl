import re

YOUTUBE_PLAYLIST_RE = re.compile(r"(?:youtube\.com|youtu\.be).*[?&]list=([A-Za-z0-9_-]+)", re.I)
YOUTUBE_VIDEO_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})", re.I
)
YOUTUBE_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

SPOTIFY_PLAYLIST_RE = re.compile(r"open\.spotify\.com/playlist/", re.I)
SPOTIFY_TRACK_RE = re.compile(r"open\.spotify\.com/track/", re.I)

SOUNDCLOUD_RE = re.compile(r"soundcloud\.com/", re.I)

INSTAGRAM_RE = re.compile(r"^https?://(www\.)?instagram\.com/.+", re.I)
FACEBOOK_RE = re.compile(r"^https?://(www\.|web\.|m\.)?(facebook\.com|fb\.watch)/.+", re.I)
THREADS_RE = re.compile(r"^https?://(www\.)?threads\.(net|com)/.+", re.I)
BLUESKY_RE = re.compile(r"^https?://(www\.)?bsky\.app/.+", re.I)
TIKTOK_RE = re.compile(r"^https?://(www\.|vm\.|vt\.)?tiktok\.com/.+", re.I)
TWITTER_RE = re.compile(r"^https?://(www\.)?(twitter\.com|x\.com)/.+", re.I)

# Ordered (platform_kind, regex) — first match wins. Shared by the plain-text
# handler and the inline-query handler so both recognize the same links.
SOCIAL_PATTERNS = [
    ("instagram", INSTAGRAM_RE),
    ("facebook", FACEBOOK_RE),
    ("threads", THREADS_RE),
    ("bluesky", BLUESKY_RE),
    ("tiktok", TIKTOK_RE),
    ("twitter", TWITTER_RE),
]

URL_RE = re.compile(r"https?://\S+", re.I)


def classify_message(text: str) -> tuple[str, str]:
    """Returns (kind, value) where kind is one of:
    'youtube_playlist', 'youtube_video', 'spotify_playlist', 'spotify_track',
    'soundcloud', 'instagram', 'facebook', 'threads', 'bluesky', 'tiktok',
    'twitter', 'unsupported_url', 'search'. `value` is the relevant link/id/query.
    """
    text = text.strip()

    if SPOTIFY_PLAYLIST_RE.search(text):
        return "spotify_playlist", text
    if SPOTIFY_TRACK_RE.search(text):
        return "spotify_track", text
    if YOUTUBE_PLAYLIST_RE.search(text):
        return "youtube_playlist", text
    if YOUTUBE_VIDEO_RE.search(text) or YOUTUBE_BARE_ID_RE.match(text):
        return "youtube_video", text
    if SOUNDCLOUD_RE.search(text):
        return "soundcloud", text

    for kind, pattern in SOCIAL_PATTERNS:
        if pattern.match(text):
            return kind, text

    if URL_RE.match(text):
        # Some other URL we don't understand — treat as unsupported rather
        # than silently searching YouTube for a raw link.
        return "unsupported_url", text

    return "search", text


def sanitize_filename(name: str, max_len: int = 150) -> str:
    name = name or "track"
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] or "track"


def duration_to_seconds(duration) -> int:
    """Accepts 'HH:MM:SS', 'MM:SS', or an int/float already in seconds."""
    if duration is None:
        return 0
    if isinstance(duration, (int, float)):
        return int(duration)
    try:
        parts = [int(p) for p in str(duration).strip().split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def truncate(text: str, length: int) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def guess_kind_from_ext(ext: str) -> str:
    """Rough classification used to pick send_audio/send_video/send_photo
    for platforms we don't force-convert (i.e. everything but YouTube)."""
    ext = (ext or "").lower().lstrip(".")
    if ext in {"mp3", "m4a", "aac", "ogg", "opus", "wav", "flac"}:
        return "audio"
    if ext in {"mp4", "mov", "mkv", "webm", "m3u8", "ts"}:
        return "video"
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"
    return "document"
