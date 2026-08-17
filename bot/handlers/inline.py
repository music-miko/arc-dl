# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
import os
import re
import uuid
from urllib.parse import urlparse

from pyrogram.handlers import InlineQueryHandler
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultAudio,
    InlineQueryResultCachedAudio,
    InlineQueryResultCachedDocument,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedVideo,
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


class InlineSearcher:
    def __init__(self):
        self.search_limit = 5
        self.resolve_timeout = 4.5
        self.answer_budget = 6.0
        self.default_thumb = "https://placehold.co/200x200/png?text=No+Thumbnail"
        self.skip_kinds = ("youtube_playlist", "spotify_playlist", "unsupported_url")
        self.telegram_link_re = re.compile(r"https?://(?:t\.me|telegram\.dog)/(?P<uname>[A-Za-z0-9_]+)/(?P<mid>\d+)")
        self.telegram_media_kinds = (
            ("audio", "audio"),
            ("voice", "audio"),
            ("video", "video"),
            ("animation", "video"),
            ("photo", "photo"),
            ("video_note", "video"),
            ("document", "document"),
        )

    def _youtube_thumb(self, video_id: str) -> str:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    def _caption(self, title: str, artist: str = "") -> str:
        caption = title or ""
        if artist:
            caption += f"\n{artist}"
        caption += f"\n\n@{keyboards.channel_username}"
        return caption

    def _guess_media_kind(self, url: str, default: str = "video") -> str:
        ext = os.path.splitext(urlparse(url).path)[1]
        kind = guess_kind_from_ext(ext)
        return kind if kind in ("audio", "video", "photo") else default

    def _youtube_candidate(self, hit: dict) -> dict:
        return {
            "type": "youtube",
            "video_id": hit["video_id"],
            "_kind": "audio",
            "title": hit.get("title") or "YouTube Audio",
            "artist": hit.get("channel", ""),
            "duration": hit.get("duration"),
            "thumbnail": hit.get("thumbnail") or self._youtube_thumb(hit["video_id"]),
        }

    async def _build_candidates(self, kind: str, value: str) -> list[dict]:
        if kind == "youtube_video":
            try:
                hits = await yt_api.search_youtube(value, limit=1)
            except YTAPIError:
                hits = []
            return [self._youtube_candidate(hits[0])] if hits else []

        if kind == "spotify_track":
            return [{"type": "spotify", "url": value, "_kind": "audio", "title": "Spotify Track"}]

        if kind == "soundcloud":
            return [{"type": "soundcloud_direct_link", "url": value, "_kind": "audio", "title": "SoundCloud Track"}]

        if kind in classifier.social_kinds:
            label = classifier.social_labels[kind]
            return [{"type": kind, "url": value, "_kind": "video", "title": label}]

        try:
            hits = await yt_api.search_youtube(value, limit=self.search_limit)
        except YTAPIError:
            hits = []
        return [self._youtube_candidate(h) for h in hits]

    def _detect_message_media(self, msg):
        for attr, kind in self.telegram_media_kinds:
            media = getattr(msg, attr, None)
            if media:
                return media, kind
        return None, None

    async def _cached_result(self, cdn_url: str, entry: dict):
        match = self.telegram_link_re.match(cdn_url)
        if not match:
            return None

        username, message_id = match.group("uname"), int(match.group("mid"))
        try:
            msg = await app.get_messages(username, message_id)
        except Exception as e:
            LOGGER.debug("Inline telegram lookup failed for %s/%s: %s", username, message_id, e)
            return None

        media, kind = self._detect_message_media(msg)
        if not media:
            return None

        title = entry.get("title") or "Untitled"
        artist = entry.get("artist") or entry.get("channel") or ""
        caption = self._caption(title, artist)
        result_id = uuid.uuid4().hex[:16]

        if kind == "audio":
            return InlineQueryResultCachedAudio(id=result_id, audio_file_id=media.file_id, caption=caption)
        if kind == "video":
            return InlineQueryResultCachedVideo(
                id=result_id, video_file_id=media.file_id, title=truncate(title, 60), caption=caption,
            )
        if kind == "photo":
            return InlineQueryResultCachedPhoto(id=result_id, photo_file_id=media.file_id, caption=caption)
        return InlineQueryResultCachedDocument(
            id=result_id, document_file_id=media.file_id, title=truncate(title, 60), caption=caption,
        )

    def _url_result(self, cdn_url: str, entry: dict):
        kind = entry.get("_kind") or "audio"
        title = entry.get("title") or "Untitled"
        artist = entry.get("artist") or entry.get("channel") or ""
        thumb = entry.get("thumbnail") or self.default_thumb
        caption = self._caption(title, artist)
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
                id=result_id, photo_url=cdn_url, thumb_url=thumb, title=truncate(title, 60), caption=caption,
            )

        return InlineQueryResultAudio(
            id=result_id,
            audio_url=cdn_url,
            title=truncate(title, 60),
            performer=truncate(artist, 60) if artist else "",
            audio_duration=duration_to_seconds(entry.get("duration")) or None,
            caption=caption,
        )

    async def _resolve_one(self, entry: dict):
        resolved = await resolve_cdn_fast(entry)
        if not resolved or not resolved[0]:
            return None

        cdn_url, entry = resolved
        cached = await self._cached_result(cdn_url, entry)
        if cached:
            return cached

        if entry.get("type") in classifier.social_kinds:
            entry = {**entry, "_kind": self._guess_media_kind(cdn_url, default="video")}
        return self._url_result(cdn_url, entry)

    async def _resolve(self, entry: dict):
        try:
            return await asyncio.wait_for(self._resolve_one(entry), timeout=self.resolve_timeout)
        except Exception as e:
            LOGGER.debug("Inline resolve dropped for %s: %s", entry.get("type"), e)
            return None

    async def _gather_results(self, kind: str, value: str) -> list:
        candidates = await self._build_candidates(kind, value)
        if not candidates:
            return []
        resolved = await asyncio.gather(*(self._resolve(c) for c in candidates))
        return [r for r in resolved if r]

    async def answer(self, inline_query: InlineQuery) -> None:
        query = inline_query.query.strip()

        if not query:
            await inline_query.answer(results=[], cache_time=1)
            return

        kind, value = classifier.classify(query)

        if kind in self.skip_kinds:
            await inline_query.answer(results=[], cache_time=1)
            return

        try:
            results = await asyncio.wait_for(self._gather_results(kind, value), timeout=self.answer_budget)
        except Exception as e:
            LOGGER.warning("Inline search failed for %r: %s", query, e)
            results = []

        await inline_query.answer(results=results, cache_time=5, is_personal=True)


inline_searcher = InlineSearcher()


async def inline_search(client, inline_query: InlineQuery):
    await inline_searcher.answer(inline_query)


HANDLERS = [
    (InlineQueryHandler, inline_search, None),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
