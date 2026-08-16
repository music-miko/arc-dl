# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Inline mode.

Every result here carries the actual media — audio as
InlineQueryResultAudio, a photo as InlineQueryResultPhoto, or anything
else (mostly social-platform video) as InlineQueryResultDocument —
fetched from Arc API and resolved to a real cdn url before the query is
answered. There's no "Download" button and no deep link into a private
chat: if we can hand over the file directly, there's no reason to make
the user tap through to get it.

Every candidate's cdn url is probed for its real Content-Type before
it's added to the answer. Telegram validates that itself when it fetches
the url, and one bad result — most commonly a raw opus/webm stream
mislabeled as an mp3 — makes it reject the *entire* batch with
FileContentTypeInvalid, silently dropping every other result along with
it. Dropping just the one bad result here is far cheaper than losing all
of them.

The trade-off is speed, not correctness: resolving a cdn url means an
actual Arc API call (and, for an uncached YouTube video, a scrape) plus
this probe, so each candidate is resolved with a short per-item timeout
and silently dropped if it doesn't come back in time, rather than
holding up the whole inline query for one slow result.
"""

import asyncio

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
from ..utils.format import duration_to_seconds, truncate
from ..utils.mime import sniffer


class InlineResolver:
    """Everything inline mode needs to turn a cached result entry into a
    real, type-verified InlineQueryResult. The per-item resolve timeout
    and the CDN probe headers live as `self.xxx` here, since this is the
    only file that needs either."""

    def __init__(self):
        self.resolve_timeout = 8.0
        self.probe_headers = {"Accept": "*/*"}

    async def resolve(self, entry: dict) -> tuple[str, dict] | None:
        """resolve_cdn() with a short timeout, returning None on any
        failure — a slow or broken result is simply left out of the
        inline answer."""
        try:
            cdn_url, entry = await asyncio.wait_for(resolve_cdn(entry), timeout=self.resolve_timeout)
        except Exception:
            return None

        if not cdn_url:
            return None
        if downloader.telegram_cdn_re.match(cdn_url):
            # A Telegram-cached message reference, not a real fetchable
            # url — inline results need an actual url, so this can't be
            # used directly. Fine to skip; the private chat still handles it.
            return None

        return cdn_url, entry

    async def audio_result(
        self, cdn_url: str, title: str, artist: str = "", duration=None,
    ) -> InlineQueryResultAudio | None:
        """Only returns a result once the url's real Content-Type has
        been confirmed as audio. Telegram fetches audio_url itself and
        rejects the whole batch if it turns out to be something else, so
        that's verified here instead of assumed."""
        kind, _ = await sniffer.probe_remote(cdn_url, self.probe_headers)
        if kind != "audio":
            return None

        return InlineQueryResultAudio(
            audio_url=cdn_url,
            title=truncate(title or "Audio", 60),
            performer=truncate(artist, 60) if artist else "",
            audio_duration=duration_to_seconds(duration),
        )

    async def media_result(self, cdn_url: str, title: str):
        """Photo or Document, decided from the url's real Content-Type —
        never guessed from the url path, since social platforms are
        inconsistent about serving a useful extension. Returns None (and
        drops the candidate) when the Content-Type isn't recognizably
        visual media, rather than guessing a mime type Telegram might
        reject."""
        kind, content_type = await sniffer.probe_remote(cdn_url, self.probe_headers)

        if kind == "photo":
            return InlineQueryResultPhoto(photo_url=cdn_url, title=title)
        if kind == "video":
            return InlineQueryResultDocument(document_url=cdn_url, title=title, mime_type=content_type)

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
            cdn_url, _ = resolved
            result = await inline_resolver.media_result(cdn_url, classifier.social_labels[kind])
            if result:
                results.append(result)

    elif kind == "unsupported_url":
        pass  # no results — falls through to the "no results" switch_pm below

    else:  # plain-text search — resolve a handful of hits concurrently
        try:
            hits = await yt_api.search_youtube(value, limit=3)
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
