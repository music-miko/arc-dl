# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""Everything that builds a keyboard, a button, or an inline-query result
lives in this one file — result/pagination/start keyboards, the clone
management keyboard + list renderer, the clone reply-keyboard button, and
the inline-mode search/result/edit flow — instead of being split one
concept per file."""


import re

from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    KeyboardButtonRequestManagedBot,
    ReplyKeyboardMarkup,
)

from .. import LOGGER
from ..core.clones import clones
from ..core.mongo import mongo
from ..dl.api_client import YTAPIError, yt_api
from .classifier import classifier
from .common import truncate
from .texts import NO_CLONES_TEXT, YOUR_CLONES_TEXT


class KeyboardBuilder:
    def __init__(self):
        self.playlist_page_size = 8
        self.channel_username = "ArcUpdates"
        self.channel_url = f"https://telegram.dog/{self.channel_username}"

    def results_keyboard(self, entries: list[tuple[str, dict]]) -> InlineKeyboardMarkup:
        rows = []
        for token, meta in entries:
            label = truncate(meta.get("title") or "Untitled", 45)
            duration = meta.get("duration")
            if duration:
                label = f"{label} - {duration}"
            rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}")])
        return InlineKeyboardMarkup(rows)

    def paginated_results_keyboard(
        self, list_token: str, entries: list[tuple[str, dict]], page: int
    ) -> InlineKeyboardMarkup:
        page_size = self.playlist_page_size
        total_pages = max(1, (len(entries) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))

        start = page * page_size
        page_entries = entries[start:start + page_size]

        rows = []
        for token, meta in page_entries:
            label = truncate(meta.get("title") or "Untitled", 40)
            duration = meta.get("duration")
            if duration:
                label = f"{label} - {duration}"
            rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("< Prev", callback_data=f"list:{list_token}:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next >", callback_data=f"list:{list_token}:{page + 1}"))
        if len(nav) > 1:
            rows.append(nav)

        return InlineKeyboardMarkup(rows)

    def start_keyboard(self, bot_username: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        ])


keyboards = KeyboardBuilder()


def build_clone_list_keyboard(docs: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for doc in docs:
        bot_id = doc["_id"]
        username = doc.get("username") or str(bot_id)
        running = bot_id in clones.active
        rows.append([InlineKeyboardButton(f"@{username} — {'Running' if running else 'Stopped'}", callback_data="noop")])
        rows.append([
            InlineKeyboardButton("⏹ Stop" if running else "▶️ Start", callback_data=f"mybot_toggle:{bot_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"mybot_delete:{bot_id}"),
        ])
    return InlineKeyboardMarkup(rows)


async def render_clone_list(owner_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    docs = await mongo.clones_for_owner(owner_id)
    if not docs:
        return NO_CLONES_TEXT, None
    return YOUR_CLONES_TEXT, build_clone_list_keyboard(docs)


def suggest_clone_username(user) -> str:
    base = re.sub(r"[^a-zA-Z0-9]", "", (user.first_name or "user")).lower()[:20] or "user"
    return f"{base}_arc_downloader_bot"[:32]


def build_clone_keyboard(user) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                "🤖 Clone this bot",
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    button_id=1,
                    suggested_name=f"{(user.first_name or 'My').strip()}'s Arc Downloader"[:64],
                    suggested_username=suggest_clone_username(user),
                ),
            )
        ]],
        resize_keyboard=True,
    )


# --- Inline mode: search candidates, the result card, and safe editing ---

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
