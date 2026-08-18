# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from .. import LOGGER
from ..dl.api_client import YTAPIError, yt_api
from .classifier import classifier
from .format import truncate

SEARCH_LIMIT = 5
DEFAULT_THUMB = "https://placehold.co/200x200/png?text=No+Thumbnail"


def _youtube_thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _youtube_candidate(hit: dict) -> dict:
    return {
        "type": "youtube",
        "video_id": hit["video_id"],
        "title": hit.get("title") or "YouTube Audio",
        "artist": hit.get("channel", ""),
        "duration": hit.get("duration"),
        "thumbnail": hit.get("thumbnail") or _youtube_thumb(hit["video_id"]),
    }


async def build_candidates(kind: str, value: str) -> list[dict]:
    if kind == "youtube_video":
        try:
            hits = await yt_api.search_youtube(value, limit=1)
        except YTAPIError:
            hits = []
        return [_youtube_candidate(hits[0])] if hits else []

    if kind == "spotify_track":
        return [{"type": "spotify", "url": value, "title": "Spotify Track"}]

    if kind == "soundcloud":
        return [{"type": "soundcloud_direct_link", "url": value, "title": "SoundCloud Track"}]

    if kind in classifier.social_kinds:
        label = classifier.social_labels[kind]
        return [{"type": kind, "url": value, "title": label}]

    try:
        hits = await yt_api.search_youtube(value, limit=SEARCH_LIMIT)
    except YTAPIError:
        hits = []
    return [_youtube_candidate(h) for h in hits]


def build_result(token: str, entry: dict) -> InlineQueryResultArticle:
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    thumb = entry.get("thumbnail") or DEFAULT_THUMB

    body = title
    if artist:
        body += f"\n{artist}"
    body += "\n\nTap Download below to fetch this."

    return InlineQueryResultArticle(
        id=token,
        title=truncate(title, 60),
        description=truncate(artist, 60) if artist else "Tap to fetch this",
        thumb_url=thumb,
        input_message_content=InputTextMessageContent(body),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬇️ Download", callback_data=f"idl:{token}")]]
        ),
    )


async def safe_edit_inline_text(client, inline_message_id: str, text: str) -> None:
    try:
        await client.edit_inline_text(inline_message_id, text)
    except Exception as e:
        LOGGER.debug("Could not edit inline message: %s", e)
