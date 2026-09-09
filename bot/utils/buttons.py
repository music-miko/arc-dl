# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

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
from ..locale import default_lang, language_names, supported_langs, text
from .classifier import classifier
from .helper import truncate


class KeyboardBuilder:
    def __init__(self):
        self.playlist_page_size = 8
        self.updates_channel_url = "https://t.me/ArcUpdates"

    def updates_channel_row(self, lang: str = default_lang) -> list[InlineKeyboardButton]:
        return [InlineKeyboardButton(text("btn_updates_channel", lang), url=self.updates_channel_url)]

    def updates_channel_markup(self, lang: str = default_lang) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([self.updates_channel_row(lang)])

    def with_updates_channel(self, markup: InlineKeyboardMarkup | None, lang: str = default_lang) -> InlineKeyboardMarkup:
        rows = list(markup.inline_keyboard) if markup else []
        rows.append(self.updates_channel_row(lang))
        return InlineKeyboardMarkup(rows)

    def results_keyboard(self, entries: list[tuple[str, dict]], lang: str = default_lang) -> InlineKeyboardMarkup:
        rows = []
        for token, meta in entries:
            label = truncate(meta.get("title") or "Untitled", 45)
            duration = meta.get("duration")
            if duration:
                label = f"{label} - {duration}"
            rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}")])
        return InlineKeyboardMarkup(rows)

    def paginated_results_keyboard(
        self, list_token: str, entries: list[tuple[str, dict]], page: int, lang: str = default_lang
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
            nav.append(InlineKeyboardButton(text("btn_prev", lang), callback_data=f"list:{list_token}:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text("btn_next", lang), callback_data=f"list:{list_token}:{page + 1}"))
        if len(nav) > 1:
            rows.append(nav)

        return InlineKeyboardMarkup(rows)

    def start_keyboard(self, bot_username: str, lang: str = default_lang) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text("btn_add_to_group", lang), url=f"https://t.me/{bot_username}?startgroup=true")],
            self.updates_channel_row(lang),
        ])

    def lang_keyboard(self) -> InlineKeyboardMarkup:
        rows = []
        row = []
        for code in supported_langs:
            row.append(InlineKeyboardButton(language_names[code], callback_data=f"setlang:{code}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return InlineKeyboardMarkup(rows)


keyboards = KeyboardBuilder()


def build_clone_list_keyboard(docs: list[dict], lang: str = default_lang) -> InlineKeyboardMarkup:
    rows = []
    for doc in docs:
        bot_id = doc["_id"]
        username = doc.get("username") or str(bot_id)
        running = bot_id in clones.active
        status_label = text("status_running", lang) if running else text("status_stopped", lang)
        rows.append([InlineKeyboardButton(f"@{username} — {status_label}", callback_data="noop")])
        rows.append([
            InlineKeyboardButton(
                text("btn_stop", lang) if running else text("btn_start", lang),
                callback_data=f"mybot_toggle:{bot_id}",
            ),
            InlineKeyboardButton(text("btn_delete", lang), callback_data=f"mybot_delete:{bot_id}"),
        ])
    return InlineKeyboardMarkup(rows)


async def render_clone_list(owner_id: int, lang: str = default_lang) -> tuple[str, InlineKeyboardMarkup | None]:
    docs = await mongo.clones_for_owner(owner_id)
    if not docs:
        return text("no_clones_text", lang), None
    return text("your_clones_text", lang), build_clone_list_keyboard(docs, lang)


def suggest_clone_username(user) -> str:
    base = re.sub(r"[^a-zA-Z0-9]", "", (user.first_name or "user")).lower()[:20] or "user"
    return f"{base}_arc_downloader_bot"[:32]


def build_clone_keyboard(user, lang: str = default_lang) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                text("btn_clone_this_bot", lang),
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    button_id=1,
                    suggested_name=f"{(user.first_name or 'My').strip()}'s Arc Downloader"[:64],
                    suggested_username=suggest_clone_username(user),
                ),
            )
        ]],
        resize_keyboard=True,
    )


class InlineSearch:
    def __init__(self):
        self.search_limit = 5
        self.default_thumb = "https://graph.org/file/d3c072a02035a883a717d-c55ae1cc21e629e39e.jpg"

    def youtube_thumb(self, video_id: str) -> str:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    def youtube_candidate(self, hit: dict) -> dict:
        return {
            "type": "youtube",
            "video_id": hit["video_id"],
            "title": hit.get("title") or "YouTube Audio",
            "artist": hit.get("channel", ""),
            "duration": hit.get("duration"),
            "thumbnail": hit.get("thumbnail") or self.youtube_thumb(hit["video_id"]),
        }

    async def build_candidates(self, kind: str, value: str) -> list[dict]:
        from ..dl.api_client import YTAPIError, yt_api

        if kind == "youtube_video":
            try:
                hits = await yt_api.search_youtube(value, limit=1)
            except YTAPIError:
                hits = []
            return [self.youtube_candidate(hits[0])] if hits else []

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
            hits = await yt_api.search_youtube(value, limit=self.search_limit)
        except YTAPIError:
            hits = []
        return [self.youtube_candidate(h) for h in hits]

    def build_result(self, token: str, entry: dict, lang: str = default_lang) -> InlineQueryResultArticle:
        title = entry.get("title") or "Untitled"
        artist = entry.get("artist") or entry.get("channel") or ""
        thumb = entry.get("thumbnail") or self.default_thumb

        body = title
        if artist:
            body += f"\n{artist}"
        body += f"\n\n{text('inline_download_body_text', lang)}"

        return InlineQueryResultArticle(
            id=token,
            title=truncate(title, 60),
            description=truncate(artist, 60) if artist else text("inline_download_hint_text", lang),
            thumb_url=thumb,
            input_message_content=InputTextMessageContent(body),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text("btn_download", lang), callback_data=f"idl:{token}")], keyboards.updates_channel_row(lang)]
            ),
        )

    async def safe_edit_inline_text(self, client, inline_message_id: str, text: str) -> None:
        try:
            await client.edit_inline_text(inline_message_id, text)
        except Exception as e:
            LOGGER.debug("Could not edit inline message: %s", e)


inline_search = InlineSearch()


class TeraboxPresenter:
    def format_size(self, num_bytes) -> str | None:
        try:
            size = float(num_bytes)
        except (TypeError, ValueError):
            return None
        if size <= 0:
            return None
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def build_caption(self, f: dict) -> str:
        lines = [f"📁 {f.get('name') or 'Terabox file'}"]
        size_label = self.format_size(f.get("size"))
        if size_label:
            lines.append(f"💾 {size_label}")
        if f.get("duration"):
            lines.append(f"⏱ {f['duration']}")
        return "\n".join(lines)

    def build_buttons(self, f: dict, lang: str = default_lang) -> InlineKeyboardMarkup:
        rows = []

        dl_cdn = f.get("dl_cdn")
        if dl_cdn:
            rows.append([InlineKeyboardButton(text("btn_download", lang), url=dl_cdn)])

        cdn_map = {q: link for q, link in (f.get("cdn") or {}).items() if link}
        ordered_qualities = sorted(cdn_map, key=lambda q: int(re.sub(r"\D", "", q) or 0))
        watch_buttons = [
            InlineKeyboardButton(text("btn_watch", lang, n=i), url=cdn_map[q])
            for i, q in enumerate(ordered_qualities, start=1)
        ]
        for i in range(0, len(watch_buttons), 2):
            rows.append(watch_buttons[i:i + 2])

        return keyboards.with_updates_channel(InlineKeyboardMarkup(rows) if rows else None, lang)


terabox_presenter = TeraboxPresenter()
