# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, InlineQueryHandler
from pyrogram.types import CallbackQuery, InlineQuery

from .. import LOGGER
from ..core.client import app
from ..core.mongo import mongo
from ..dl.actions import resolve_cdn
from ..dl.api_client import YTAPIError
from ..dl.downloader import downloader
from ..locale import text as t
from ..utils.buttons import inline_search
from ..utils.classifier import classifier
from ..utils.helper import cache
from . import inline_registry as registry


@registry.on(InlineQueryHandler)
async def search(client, inline_query: InlineQuery):
    lang = await mongo.get_lang(inline_query.from_user.id) if inline_query.from_user else "en"
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer(
            results=[],
            switch_pm_text=t("inline_placeholder_text", lang),
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    kind, value = classifier.classify(query)

    if kind in ("youtube_playlist", "spotify_playlist", "applemusic_playlist", "jiosaavn_playlist"):
        await inline_query.answer(
            results=[],
            switch_pm_text=t("inline_playlist_pm_text", lang),
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    if kind == "terabox":
        await inline_query.answer(
            results=[],
            switch_pm_text=t("inline_terabox_pm_text", lang),
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    if kind == "unsupported_url":
        await inline_query.answer(results=[], cache_time=1)
        return

    candidates = await inline_search.build_candidates(kind, value)
    if not candidates:
        await inline_query.answer(
            results=[],
            cache_time=5,
            switch_pm_text=t("inline_no_results_pm_text", lang),
            switch_pm_parameter="hi",
        )
        return

    results = [inline_search.build_result(cache.put_new(entry), entry, lang) for entry in candidates]
    await inline_query.answer(results=results, cache_time=5, is_personal=True)


@registry.on(CallbackQueryHandler, filters.regex(r"^idl:"))
async def download(client, callback_query: CallbackQuery):
    lang = await mongo.get_lang(callback_query.from_user.id)

    if not callback_query.inline_message_id:
        await callback_query.answer(t("expired_text", lang), show_alert=True)
        return

    token = callback_query.data.split(":", 1)[1]
    entry = cache.get(token)
    if not entry:
        await callback_query.answer(t("expired_text", lang), show_alert=True)
        return

    inline_message_id = callback_query.inline_message_id
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""

    await callback_query.answer(t("starting_text", lang))
    await inline_search.safe_edit_inline_text(client, inline_message_id, f"{t('downloading_text', lang)} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        artist = entry.get("artist") or entry.get("channel") or artist
        duration = entry.get("duration")
        thumbnail = entry.get("thumbnail")
        platform = entry["type"]

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await inline_search.safe_edit_inline_text(client, inline_message_id, f"{t('sending_text', lang)} {title}")

        await downloader.deliver_to_inline(
            client, inline_message_id, cdn_url,
            title=title, artist=artist, duration=duration,
            thumbnail_url=thumbnail, platform=platform,
        )

    except YTAPIError as e:
        LOGGER.warning("Inline download failed for token=%s: %s", token, e)
        await inline_search.safe_edit_inline_text(client, inline_message_id, t("failed_text", lang, error=e))
    except Exception:
        LOGGER.exception("Unexpected error delivering inline token=%s", token)
        await inline_search.safe_edit_inline_text(client, inline_message_id, t("unexpected_error_text", lang))


registry.attach(app)
