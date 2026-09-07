# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from ftmgram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from .. import LOGGER
from ..dl.api_client import YTAPIError, yt_api
from .classifier import classifier
from .format import truncate
from .rich import build_download_rich_content

SEARCH_LIMIT = 5
DEFAULT_THUMB = "https://graph.org/file/d3c072a02035a883a717d-c55ae1cc21e629e39e.jpg"


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

    if kind == "applemusic_track":
        return [{"type": "applemusic", "url": value, "title": "Apple Music Track"}]

    if kind == "jiosaavn_track":
        return [{"type": "jiosaavn", "url": value, "title": "JioSaavn Track"}]

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

    callback_data = f"idl:{token}"

    # Bot API 10.3's InputRichBlockButtons lets the "Download" button live
    # inside the message's own rich content instead of a separate
    # reply_markup keyboard below it — and 10.1 explicitly allows
    # InputRichMessageContent as inline query InputMessageContent. Falls
    # back to the classic text + InlineKeyboardMarkup combo automatically
    # if the installed ftmgram build doesn't support it yet.
    rich_content = build_download_rich_content(body, "⬇️ Download", callback_data)
    if rich_content:
        return InlineQueryResultArticle(
            id=token,
            title=truncate(title, 60),
            description=truncate(artist, 60) if artist else "Tap to fetch this",
            thumb_url=thumb,
            input_message_content=rich_content,
        )

    return InlineQueryResultArticle(
        id=token,
        title=truncate(title, 60),
        description=truncate(artist, 60) if artist else "Tap to fetch this",
        thumb_url=thumb,
        input_message_content=InputTextMessageContent(body + "\n\nTap Download below to fetch this."),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬇️ Download", callback_data=callback_data)]]
        ),
    )


async def safe_edit_inline_text(client, inline_message_id: str, text: str) -> None:
    try:
        await client.edit_inline_text(inline_message_id, text)
    except Exception as e:
        LOGGER.debug("Could not edit inline message: %s", e)
