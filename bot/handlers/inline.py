"""
Inline mode.

Telegram never tells a bot which chat an inline result landed in once
picked, so there's no reliable way to attach a working "download now"
button directly to an inline result (that's what `on_chosen_inline_result`
+ `edit_inline_media` would need — and it also requires "inline feedback"
to be turned on for the bot in BotFather, which most bots don't have).

Instead, every result here carries a plain URL button that deep-links
back into a private chat with this bot: `t.me/<bot>?start=dl_<token>`.
Opening it starts the download there — see bot/handlers/start.py. This
works with zero special BotFather configuration and is exactly why
"downloads only happen in private chat" holds everywhere in this bot.
"""

import logging

from pyrogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from ..core.client import app
from ..dl.api_client import YTAPIError, yt_api
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.keyboards import keyboards

logger = logging.getLogger("arcdl.handlers.inline")

_SOCIAL_KINDS = {"instagram", "facebook", "threads", "bluesky", "tiktok", "twitter"}


def _pending_content(title: str) -> InputTextMessageContent:
    return InputTextMessageContent(f"{title}\n\nTap Download to fetch this in a private chat.")


@app.on_inline_query()
async def inline_search(client, inline_query: InlineQuery):
    query = inline_query.query.strip()
    bot_username = client.me.username or ""

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
        # Pagination needs a real message with buttons — not viable as a
        # single inline result. Send them to the private chat for this one.
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
            h = hits[0]
            token = cache.put_new({
                "type": "youtube", "video_id": h["video_id"],
                "title": h["title"], "artist": h.get("channel", ""),
                "duration": h.get("duration"), "thumbnail": h.get("thumbnail"),
            })
            results.append(InlineQueryResultArticle(
                id=token, title=h["title"],
                description=f"{h.get('duration', '')} - {h.get('channel', '')}",
                thumb_url=h.get("thumbnail"),
                input_message_content=_pending_content(h["title"]),
                reply_markup=keyboards.inline_download_keyboard(bot_username, token),
            ))

    elif kind == "spotify_track":
        token = cache.put_new({"type": "spotify", "url": value, "title": "Spotify Track"})
        results.append(InlineQueryResultArticle(
            id=token, title="Spotify Track", description=value,
            input_message_content=_pending_content("Spotify Track"),
            reply_markup=keyboards.inline_download_keyboard(bot_username, token),
        ))

    elif kind == "soundcloud":
        token = cache.put_new({"type": "soundcloud_direct_link", "url": value, "title": "SoundCloud Track"})
        results.append(InlineQueryResultArticle(
            id=token, title="SoundCloud Track", description=value,
            input_message_content=_pending_content("SoundCloud Track"),
            reply_markup=keyboards.inline_download_keyboard(bot_username, token),
        ))

    elif kind in _SOCIAL_KINDS:
        label = f"{kind.capitalize()} media"
        token = cache.put_new({"type": kind, "url": value, "title": label})
        results.append(InlineQueryResultArticle(
            id=token, title=label, description=value,
            input_message_content=_pending_content(label),
            reply_markup=keyboards.inline_download_keyboard(bot_username, token),
        ))

    elif kind == "unsupported_url":
        pass  # no results — falls through to the "no results" switch_pm below

    else:  # plain-text search
        try:
            hits = await yt_api.search_youtube(value, limit=5)
        except YTAPIError:
            hits = []

        for h in hits:
            token = cache.put_new({
                "type": "youtube", "video_id": h["video_id"],
                "title": h["title"], "artist": h.get("channel", ""),
                "duration": h.get("duration"), "thumbnail": h.get("thumbnail"),
            })
            results.append(InlineQueryResultArticle(
                id=token, title=h["title"],
                description=f"{h.get('duration', '')} - {h.get('channel', '')}",
                thumb_url=h.get("thumbnail"),
                input_message_content=_pending_content(h["title"]),
                reply_markup=keyboards.inline_download_keyboard(bot_username, token),
            ))

    await inline_query.answer(
        results=results,
        cache_time=30,
        is_personal=True,
        switch_pm_text=None if results else "No results — try another search or link",
        switch_pm_parameter="hi" if not results else None,
    )
