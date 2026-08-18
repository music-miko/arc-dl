# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, InlineQueryHandler
from pyrogram.types import CallbackQuery, InlineQuery

from .. import LOGGER
from ..core.client import app
from ..dl.actions import resolve_cdn
from ..dl.api_client import YTAPIError
from ..dl.downloader import downloader
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.inline_results import build_candidates, build_result, safe_edit_inline_text
from ..utils.registry import HandlerRegistry
from ..utils.texts import DOWNLOADING_TEXT, EXPIRED_TEXT, SENDING_TEXT, STARTING_TEXT

registry = HandlerRegistry(__name__)


@registry.on(InlineQueryHandler)
async def search(client, inline_query: InlineQuery):
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

    candidates = await build_candidates(kind, value)
    if not candidates:
        await inline_query.answer(
            results=[],
            cache_time=5,
            switch_pm_text="No results — try another search or link",
            switch_pm_parameter="hi",
        )
        return

    results = [build_result(cache.put_new(entry), entry) for entry in candidates]
    await inline_query.answer(results=results, cache_time=5, is_personal=True)


@registry.on(CallbackQueryHandler, filters.regex(r"^idl:"))
async def download(client, callback_query: CallbackQuery):
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
    await safe_edit_inline_text(client, inline_message_id, f"{DOWNLOADING_TEXT} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        artist = entry.get("artist") or entry.get("channel") or artist
        duration = entry.get("duration")
        thumbnail = entry.get("thumbnail")
        platform = entry["type"]

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await safe_edit_inline_text(client, inline_message_id, f"{SENDING_TEXT} {title}")

        await downloader.deliver_to_inline(
            client, inline_message_id, cdn_url,
            title=title, artist=artist, duration=duration,
            thumbnail_url=thumbnail, platform=platform,
        )

    except YTAPIError as e:
        LOGGER.warning("Inline download failed for token=%s: %s", token, e)
        await safe_edit_inline_text(client, inline_message_id, f"Failed: {e}")
    except Exception:
        LOGGER.exception("Unexpected error delivering inline token=%s", token)
        await safe_edit_inline_text(client, inline_message_id, "Something went wrong. Please try again.")


registry.attach(app)
