# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import uuid

from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from ..core.client import app
from ..dl.api_client import YTAPIError, yt_api
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.format import truncate

_SEARCH_LIMIT = 5
_DEFAULT_THUMB = "https://placehold.co/200x200/png?text=No+Thumbnail"


def _youtube_thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _download_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Download", callback_data=f"dl:{token}")]])


def _placeholder_text(title: str) -> str:
    return f"{title}\n\nTap Download below and I'll fetch this and send it right here."


def _make_result(*, title: str, description: str = "", entry: dict, thumb_url: str | None = None) -> InlineQueryResultArticle:
    token = cache.put_new(entry)
    return InlineQueryResultArticle(
        id=uuid.uuid4().hex,
        title=truncate(title or "Untitled", 60),
        description=truncate(description, 60) if description else None,
        thumb_url=thumb_url or _DEFAULT_THUMB,
        input_message_content=InputTextMessageContent(_placeholder_text(title or "Untitled")),
        reply_markup=_download_keyboard(token),
    )


def _youtube_result(hit: dict) -> InlineQueryResultArticle:
    return _make_result(
        title=hit.get("title") or "YouTube Audio",
        description=hit.get("channel", ""),
        thumb_url=hit.get("thumbnail") or _youtube_thumb(hit["video_id"]),
        entry={
            "type": "youtube",
            "video_id": hit["video_id"],
            "title": hit.get("title"),
            "artist": hit.get("channel", ""),
            "duration": hit.get("duration"),
            "thumbnail": hit.get("thumbnail"),
        },
    )


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
            results.append(_youtube_result(hits[0]))

    elif kind == "spotify_track":
        results.append(_make_result(
            title="Spotify Track",
            description="Tap to fetch and send this track",
            entry={"type": "spotify", "url": value, "title": "Spotify Track"},
        ))

    elif kind == "soundcloud":
        results.append(_make_result(
            title="SoundCloud Track",
            description="Tap to fetch and send this track",
            entry={"type": "soundcloud_direct_link", "url": value, "title": "SoundCloud Track"},
        ))

    elif kind in classifier.social_kinds:
        label = classifier.social_labels[kind]
        results.append(_make_result(
            title=label,
            description="Tap to fetch and send this media",
            entry={"type": kind, "url": value, "title": label},
        ))

    elif kind == "unsupported_url":
        pass

    else:
        try:
            hits = await yt_api.search_youtube(value, limit=_SEARCH_LIMIT)
        except YTAPIError:
            hits = []
        results = [_youtube_result(h) for h in hits]

    await inline_query.answer(
        results=results,
        cache_time=5,
        is_personal=True,
        switch_pm_text=None if results else "No results — try another search or link",
        switch_pm_parameter="hi" if not results else None,
    )
