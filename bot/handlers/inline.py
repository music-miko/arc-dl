# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio

from pyrogram.types import (
    InlineQuery,
    InlineQueryResultAudio,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
)

from ..core.client import app
from ..dl.actions import resolve_cdn
from ..dl.api_client import YTAPIError, yt_api
from ..dl.downloader import downloader
from ..utils.classifier import classifier
from ..utils.format import duration_to_seconds, truncate
from ..utils.mime import sniffer


class InlineResolver:
    def __init__(self):
        self.resolve_timeout = 60.0
        self.search_limit = 5
        self.probe_headers = {"Accept": "*/*"}
        self.default_thumb = "https://placehold.co/200x200/png?text=No+Thumbnail"

    async def resolve(self, entry: dict) -> tuple[str, dict] | None:
        try:
            cdn_url, entry = await asyncio.wait_for(resolve_cdn(entry), timeout=self.resolve_timeout)
        except Exception:
            return None

        if not cdn_url:
            return None
        if downloader.telegram_cdn_re.match(cdn_url):
            return None

        return cdn_url, entry

    async def audio_result(
        self, cdn_url: str, title: str, artist: str = "", duration=None,
    ) -> InlineQueryResultAudio | None:
        kind, _ = await sniffer.probe_remote(cdn_url, self.probe_headers)
        if kind != "audio":
            return None

        return InlineQueryResultAudio(
            audio_url=cdn_url,
            title=truncate(title or "Audio", 60),
            performer=truncate(artist, 60) if artist else "",
            audio_duration=duration_to_seconds(duration),
        )

    async def media_result(self, cdn_url: str, title: str, thumb_url: str | None = None):
        kind, content_type = await sniffer.probe_remote(cdn_url, self.probe_headers)
        thumb = thumb_url or self.default_thumb

        if kind == "photo":
            return InlineQueryResultPhoto(photo_url=cdn_url, thumb_url=thumb, title=title)
        if kind == "video":
            return InlineQueryResultVideo(
                video_url=cdn_url,
                thumb_url=thumb,
                title=title,
                mime_type=content_type or "video/mp4",
            )

        return None

    async def resolve_youtube_hit(self, hit: dict) -> InlineQueryResultAudio | None:
        resolved = await self.resolve({"type": "youtube", "video_id": hit["video_id"]})
        if not resolved:
            return None
        cdn_url, _ = resolved
        return await self.audio_result(cdn_url, hit.get("title"), hit.get("channel", ""), hit.get("duration"))


inline_resolver = InlineResolver()


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
            result = await inline_resolver.resolve_youtube_hit(hits[0])
            if result:
                results.append(result)

    elif kind == "spotify_track":
        resolved = await inline_resolver.resolve({"type": "spotify", "url": value})
        if resolved:
            cdn_url, entry = resolved
            result = await inline_resolver.audio_result(cdn_url, entry.get("title") or "Spotify Track")
            if result:
                results.append(result)

    elif kind == "soundcloud":
        resolved = await inline_resolver.resolve({"type": "soundcloud_direct_link", "url": value})
        if resolved:
            cdn_url, entry = resolved
            result = await inline_resolver.audio_result(
                cdn_url, entry.get("title") or "SoundCloud Track", entry.get("artist", "")
            )
            if result:
                results.append(result)

    elif kind in classifier.social_kinds:
        resolved = await inline_resolver.resolve({"type": kind, "url": value})
        if resolved:
            cdn_url, entry = resolved
            title = entry.get("title") or classifier.social_labels[kind]
            result = await inline_resolver.media_result(cdn_url, title, entry.get("thumbnail"))
            if result:
                results.append(result)

    elif kind == "unsupported_url":
        pass

    else:
        try:
            hits = await yt_api.search_youtube(value, limit=inline_resolver.search_limit)
        except YTAPIError:
            hits = []

        resolved = await asyncio.gather(*(inline_resolver.resolve_youtube_hit(h) for h in hits))
        results = [r for r in resolved if r]

    await inline_query.answer(
        results=results,
        cache_time=30,
        is_personal=True,
        switch_pm_text=None if results else "No results — try another search or link",
        switch_pm_parameter="hi" if not results else None,
    )
