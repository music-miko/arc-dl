# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
import os
import uuid
from urllib.parse import urlparse

from pyrogram.handlers import InlineQueryHandler
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultAudio,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
)

from .. import LOGGER
from ..core.client import app
from ..dl.actions import resolve_cdn_fast
from ..dl.api_client import YTAPIError, yt_api
from ..utils.classifier import classifier
from ..utils.format import duration_to_seconds, guess_kind_from_ext, truncate
from ..utils.keyboards import keyboards

_SEARCH_LIMIT = 5
_DEFAULT_THUMB = "https://placehold.co/200x200/png?text=No+Thumbnail"
# Bounds how long we'll wait on any single candidate's CDN resolve before
# giving up on it — keeps the overall inline answer snappy even if one
# platform is slow.
_RESOLVE_TIMEOUT = 60.0


def _youtube_thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _caption(title: str, artist: str = "") -> str:
    caption = title or ""
    if artist:
        caption += f"\n{artist}"
    caption += f"\n\n@{keyboards.channel_username}"
    return caption


def _guess_media_kind(url: str, default: str = "video") -> str:
    ext = os.path.splitext(urlparse(url).path)[1]
    kind = guess_kind_from_ext(ext)
    return kind if kind in ("audio", "video", "photo") else default


def _youtube_candidate(hit: dict) -> dict:
    return {
        "type": "youtube",
        "video_id": hit["video_id"],
        "_kind": "audio",
        "title": hit.get("title") or "YouTube Audio",
        "artist": hit.get("channel", ""),
        "duration": hit.get("duration"),
        "thumbnail": hit.get("thumbnail") or _youtube_thumb(hit["video_id"]),
    }


async def _build_candidates(kind: str, value: str) -> list[dict]:
    if kind == "youtube_video":
        try:
            hits = await yt_api.search_youtube(value, limit=1)
        except YTAPIError:
            hits = []
        return [_youtube_candidate(hits[0])] if hits else []

    if kind == "spotify_track":
        return [{"type": "spotify", "url": value, "_kind": "audio", "title": "Spotify Track"}]

    if kind == "soundcloud":
        return [{"type": "soundcloud_direct_link", "url": value, "_kind": "audio", "title": "SoundCloud Track"}]

    if kind in classifier.social_kinds:
        label = classifier.social_labels[kind]
        return [{"type": kind, "url": value, "_kind": "video", "title": label}]

    # Free-text search
    try:
        hits = await yt_api.search_youtube(value, limit=_SEARCH_LIMIT)
    except YTAPIError:
        hits = []
    return [_youtube_candidate(h) for h in hits]


def _build_result(cdn_url: str, entry: dict):
    kind = entry.get("_kind") or "audio"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    thumb = entry.get("thumbnail") or _DEFAULT_THUMB
    caption = _caption(title, artist)
    result_id = uuid.uuid4().hex[:16]

    if kind == "video":
        return InlineQueryResultVideo(
            id=result_id,
            video_url=cdn_url,
            thumb_url=thumb,
            mime_type="video/mp4",
            title=truncate(title, 60),
            description=truncate(artist, 60) if artist else None,
            caption=caption,
        )

    if kind == "photo":
        return InlineQueryResultPhoto(
            id=result_id,
            photo_url=cdn_url,
            thumb_url=thumb,
            title=truncate(title, 60),
            caption=caption,
        )

    return InlineQueryResultAudio(
        id=result_id,
        audio_url=cdn_url,
        title=truncate(title, 60),
        performer=truncate(artist, 60) if artist else "",
        audio_duration=duration_to_seconds(entry.get("duration")) or None,
        caption=caption,
    )


async def _resolve(entry: dict):
    try:
        resolved = await asyncio.wait_for(resolve_cdn_fast(entry), timeout=_RESOLVE_TIMEOUT)
    except Exception as e:
        LOGGER.debug("Inline resolve dropped for %s: %s", entry.get("type"), e)
        return None

    if not resolved or not resolved[0]:
        return None

    cdn_url, entry = resolved
    if entry.get("type") in classifier.social_kinds:
        entry = {**entry, "_kind": _guess_media_kind(cdn_url, default="video")}
    return cdn_url, entry


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

    if kind in ("youtube_playlist", "spotify_playlist"):
        await inline_query.answer(
            results=[],
            switch_pm_text="Open in private chat to browse this playlist",
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    if kind == "unsupported_url":
        await inline_query.answer(results=[], cache_time=1)
        return

    candidates = await _build_candidates(kind, value)
    if not candidates:
        await inline_query.answer(
            results=[],
            cache_time=5,
            switch_pm_text="No results — try another search or link",
            switch_pm_parameter="hi",
        )
        return

    # Every candidate is resolved straight to its real CDN url up front, in
    # parallel — whatever comes back is exactly what gets handed to
    # Telegram, so picking a result delivers it immediately with no
    # "Fetching..." placeholder and no separate download/upload step
    # afterwards. Anything that can't be resolved fast enough is simply
    # left out of the answer.
    resolved = await asyncio.gather(*(_resolve(c) for c in candidates))

    results = []
    for r in resolved:
        if not r:
            continue
        cdn_url, entry = r
        results.append(_build_result(cdn_url, entry))

    await inline_query.answer(
        results=results,
        cache_time=5,
        is_personal=True,
        switch_pm_text=None if results else "Couldn't fetch that right now — try again",
        switch_pm_parameter="hi" if not results else None,
    )


HANDLERS = [
    (InlineQueryHandler, inline_search, None),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
