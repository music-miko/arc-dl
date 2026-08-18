# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, InlineQueryHandler
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from .. import LOGGER
from ..core.client import app
from ..dl.actions import resolve_cdn
from ..dl.api_client import YTAPIError, yt_api
from ..dl.downloader import downloader
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.format import truncate
from ..utils.texts import DOWNLOADING_TEXT, EXPIRED_TEXT, SENDING_TEXT, STARTING_TEXT


class InlineSearchHandler:
    def __init__(self):
        self.search_limit = 5
        self.default_thumb = "https://placehold.co/200x200/png?text=No+Thumbnail"

    def _youtube_thumb(self, video_id: str) -> str:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    def _youtube_candidate(self, hit: dict) -> dict:
        return {
            "type": "youtube",
            "video_id": hit["video_id"],
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
            return [{"type": "spotify", "url": value, "title": "Spotify Track"}]

        if kind == "soundcloud":
            return [{"type": "soundcloud_direct_link", "url": value, "title": "SoundCloud Track"}]

        if kind in classifier.social_kinds:
            label = classifier.social_labels[kind]
            return [{"type": kind, "url": value, "title": label}]

        try:
            hits = await yt_api.search_youtube(value, limit=self.search_limit)
        except YTAPIError:
            hits = []
        return [self._youtube_candidate(h) for h in hits]

    def _build_result(self, token: str, entry: dict) -> InlineQueryResultArticle:
        title = entry.get("title") or "Untitled"
        artist = entry.get("artist") or entry.get("channel") or ""
        thumb = entry.get("thumbnail") or self.default_thumb

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

    async def search(self, client, inline_query: InlineQuery):
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

        candidates = await self._build_candidates(kind, value)
        if not candidates:
            await inline_query.answer(
                results=[],
                cache_time=5,
                switch_pm_text="No results — try another search or link",
                switch_pm_parameter="hi",
            )
            return

        results = [self._build_result(cache.put_new(entry), entry) for entry in candidates]

        await inline_query.answer(results=results, cache_time=5, is_personal=True)

    async def _edit_status(self, client, inline_message_id: str, text: str) -> None:
        try:
            await client.edit_inline_text(inline_message_id, text)
        except Exception as e:
            LOGGER.debug("Could not edit inline message: %s", e)

    async def download(self, client, callback_query: CallbackQuery):
        if not callback_query.inline_message_id:
            await callback_query.answer(EXPIRED_TEXT, show_alert=True)
            return

        token = callback_query.data.split(":", 1)[1]
        entry = cache.get(token)
        if not entry:
            await callback_query.answer(EXPIRED_TEXT, show_alert=True)
            return

        inline_message_id = callback_query.inline_message_id
        title = entry.get("title") or "Untitled"
        artist = entry.get("artist") or entry.get("channel") or ""

        await callback_query.answer(STARTING_TEXT)
        await self._edit_status(client, inline_message_id, f"{DOWNLOADING_TEXT} {title}")

        try:
            cdn_url, entry = await resolve_cdn(entry)
            title = entry.get("title") or title
            artist = entry.get("artist") or entry.get("channel") or artist
            duration = entry.get("duration")
            thumbnail = entry.get("thumbnail")
            platform = entry["type"]

            if not cdn_url:
                raise YTAPIError("No download link returned")

            await self._edit_status(client, inline_message_id, f"{SENDING_TEXT} {title}")

            await downloader.deliver_to_inline(
                client, inline_message_id, cdn_url,
                title=title, artist=artist, duration=duration,
                thumbnail_url=thumbnail, platform=platform,
            )

        except YTAPIError as e:
            LOGGER.warning("Inline download failed for token=%s: %s", token, e)
            await self._edit_status(client, inline_message_id, f"Failed: {e}")
        except Exception:
            LOGGER.exception("Unexpected error delivering inline token=%s", token)
            await self._edit_status(client, inline_message_id, "Something went wrong. Please try again.")


inline_handler = InlineSearchHandler()

HANDLERS = [
    (InlineQueryHandler, inline_handler.search, None),
    (CallbackQueryHandler, inline_handler.download, filters.regex(r"^idl:")),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
