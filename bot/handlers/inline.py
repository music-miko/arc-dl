"""
Inline mode.

Every result here carries the actual media — an mp3 as InlineQueryResultAudio,
an image as InlineQueryResultPhoto, or anything else (mostly social-platform
video) as InlineQueryResultDocument — fetched from Arc API and resolved to a
real cdn url before the query is answered. There's no "Download" button and
no deep link into a private chat: if we can hand over the file directly,
there's no reason to make the user tap through to get it.

The trade-off is speed, not correctness: resolving a cdn url means an actual
Arc API call (and, for an uncached YouTube video, a scrape), so each
candidate result is resolved with a short per-item timeout and silently
dropped if it doesn't come back in time, rather than holding up the whole
inline query for one slow result.
"""

import asyncio
import logging
from urllib.parse import urlparse

from pyrogram.types import (
    InlineQuery,
    InlineQueryResultAudio,
    InlineQueryResultDocument,
    InlineQueryResultPhoto,
)

from ..core.client import app
from ..dl.actions import resolve_cdn
from ..dl.api_client import YTAPIError, yt_api
from ..dl.downloader import downloader
from ..utils.classifier import classifier
from ..utils.format import duration_to_seconds, guess_kind_from_ext, truncate

logger = logging.getLogger("arcdl.handlers.inline")

_SOCIAL_KINDS = {"instagram", "facebook", "threads", "bluesky", "tiktok", "twitter"}
_SOCIAL_LABELS = {
    "instagram": "Instagram media",
    "facebook": "Facebook media",
    "threads": "Threads media",
    "bluesky": "Bluesky media",
    "tiktok": "TikTok video",
    "twitter": "Twitter/X media",
}

# How long a single result is allowed to take to resolve before it's
# dropped from the inline query rather than stalling every other result.
_RESOLVE_TIMEOUT = 8.0

# Extension -> mime type, for the InlineQueryResultDocument fallback used
# for anything that isn't confirmed audio or a photo (mostly social-platform
# video, which Telegram still plays inline for most clients when the mime
# type is set correctly).
_EXT_MIME = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mkv": "video/x-matroska", ".m4a": "audio/mp4", ".mp3": "audio/mpeg",
}


async def _resolve(entry: dict) -> tuple[str, dict] | None:
    """resolve_cdn() with a short timeout, returning None on any failure —
    a slow or broken result is simply left out of the inline answer."""
    try:
        cdn_url, entry = await asyncio.wait_for(resolve_cdn(entry), timeout=_RESOLVE_TIMEOUT)
    except Exception:
        return None

    if not cdn_url:
        return None
    if downloader.telegram_cdn_re.match(cdn_url):
        # A Telegram-cached message reference, not a real fetchable file
        # url — inline results need an actual url, so this can't be used
        # directly. Fine to skip; the private chat still handles it.
        return None

    return cdn_url, entry


def _audio_result(cdn_url: str, title: str, artist: str = "", duration=None) -> InlineQueryResultAudio:
    return InlineQueryResultAudio(
        audio_url=cdn_url,
        title=truncate(title or "Audio", 60),
        performer=truncate(artist, 60) if artist else "",
        audio_duration=duration_to_seconds(duration),
    )


def _media_result(cdn_url: str, title: str):
    """Photo or Document, depending on what the cdn url's extension says
    this actually is — social platforms don't return a content type up
    front, so this is a best-effort guess from the url path alone."""
    path = urlparse(cdn_url).path
    ext = f".{path.rsplit('.', 1)[-1].lower()}" if "." in path else ""
    kind = guess_kind_from_ext(ext)

    if kind == "photo":
        return InlineQueryResultPhoto(photo_url=cdn_url, title=title)

    return InlineQueryResultDocument(
        document_url=cdn_url,
        title=title,
        mime_type=_EXT_MIME.get(ext, "video/mp4"),
    )


async def _resolve_youtube_hit(hit: dict) -> InlineQueryResultAudio | None:
    resolved = await _resolve({"type": "youtube", "video_id": hit["video_id"]})
    if not resolved:
        return None
    cdn_url, _ = resolved
    return _audio_result(cdn_url, hit.get("title"), hit.get("channel", ""), hit.get("duration"))


@app.on_inline_query()
async def inline_search(client, inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer(
            results=[],
            switch_pm_text="Type a song name or paste a link",
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    kind, value = classifier.classify(query)
    results = []

    if kind in ("youtube_playlist", "spotify_playlist"):
        # A playlist needs a stateful, paginated pick-a-track flow — not
        # something a single inline result can offer. Send them to the
        # private chat, where picking a track downloads and sends it
        # directly (no button hop after that either).
        await inline_query.answer(
            results=[],
            switch_pm_text="Open in private chat to browse this playlist",
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    if kind == "youtube_video":
        try:
            hits = await yt_api.search_youtube(value, limit=1)
        except YTAPIError:
            hits = []
        if hits:
            result = await _resolve_youtube_hit(hits[0])
            if result:
                results.append(result)

    elif kind == "spotify_track":
        resolved = await _resolve({"type": "spotify", "url": value})
        if resolved:
            cdn_url, entry = resolved
            results.append(_audio_result(cdn_url, entry.get("title") or "Spotify Track"))

    elif kind == "soundcloud":
        resolved = await _resolve({"type": "soundcloud_direct_link", "url": value})
        if resolved:
            cdn_url, entry = resolved
            results.append(_audio_result(cdn_url, entry.get("title") or "SoundCloud Track", entry.get("artist", "")))

    elif kind in _SOCIAL_KINDS:
        resolved = await _resolve({"type": kind, "url": value})
        if resolved:
            cdn_url, _ = resolved
            results.append(_media_result(cdn_url, _SOCIAL_LABELS[kind]))

    elif kind == "unsupported_url":
        pass  # no results — falls through to the "no results" switch_pm below

    else:  # plain-text search — resolve a handful of hits concurrently
        try:
            hits = await yt_api.search_youtube(value, limit=3)
        except YTAPIError:
            hits = []

        resolved = await asyncio.gather(*(_resolve_youtube_hit(h) for h in hits))
        results = [r for r in resolved if r]

    await inline_query.answer(
        results=results,
        cache_time=30,
        is_personal=True,
        switch_pm_text=None if results else "No results — try another search or link",
        switch_pm_parameter="hi" if not results else None,
    )
