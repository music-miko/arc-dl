from pyrogram.types import (
    ChosenInlineResult,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from bot import cache
from bot.actions import run_download
from bot.api_client import YTAPIError, yt_api
from bot.client import app
from bot.utils import classify_message

_SOCIAL_KINDS = {"instagram", "facebook", "threads", "bluesky", "tiktok", "twitter"}
_SOCIAL_TITLES = {
    "instagram": "📸 Instagram", "facebook": "📘 Facebook", "threads": "🧵 Threads",
    "bluesky": "🦋 Bluesky", "tiktok": "🎵 TikTok", "twitter": "🐦 Twitter / X",
}


def _pending_content(title: str) -> InputTextMessageContent:
    # No download button here on purpose — picking the result itself
    # triggers on_chosen_inline_result below, which edits this exact
    # message in place once the file's ready. Telegram's inline feedback
    # (chosen_inline_result + inline_message_id) lets us edit a message
    # regardless of which chat it landed in, so a live callback works fine
    # here — no deep link needed.
    return InputTextMessageContent(f"⏳ **{title}**\n\nFetching…")


@app.on_inline_query()
async def inline_search(client, inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer(
            results=[],
            switch_pm_text="Type a song name or paste a link 🎵",
            switch_pm_parameter="hi",
            cache_time=1,
        )
        return

    kind, value = classify_message(query)
    results = []

    if kind in ("youtube_playlist", "spotify_playlist"):
        # Pagination needs a real message with buttons — not viable as a
        # single inline result. Send them to the private chat for this one.
        await inline_query.answer(
            results=[],
            switch_pm_text="Open in private chat to browse this playlist ▶️",
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
                description=f"{h.get('duration', '')} • {h.get('channel', '')}",
                thumb_url=h.get("thumbnail"),
                input_message_content=_pending_content(h["title"]),
            ))

    elif kind == "spotify_track":
        token = cache.put_new({"type": "spotify", "url": value, "title": "Spotify Track"})
        results.append(InlineQueryResultArticle(
            id=token, title="🎧 Spotify Track", description=value,
            input_message_content=_pending_content("Spotify Track"),
        ))

    elif kind == "soundcloud":
        token = cache.put_new({"type": "soundcloud_direct_link", "url": value, "title": "SoundCloud Track"})
        results.append(InlineQueryResultArticle(
            id=token, title="☁️ SoundCloud Track", description=value,
            input_message_content=_pending_content("SoundCloud Track"),
        ))

    elif kind in _SOCIAL_KINDS:
        label = _SOCIAL_TITLES[kind]
        token = cache.put_new({"type": kind, "url": value, "title": label})
        results.append(InlineQueryResultArticle(
            id=token, title=label, description=value,
            input_message_content=_pending_content(label),
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
                description=f"{h.get('duration', '')} • {h.get('channel', '')}",
                thumb_url=h.get("thumbnail"),
                input_message_content=_pending_content(h["title"]),
            ))

    await inline_query.answer(
        results=results,
        cache_time=30,
        is_personal=True,
        switch_pm_text=None if results else "No results — try another search or link",
        switch_pm_parameter="hi" if not results else None,
    )


@app.on_chosen_inline_result()
async def chosen_result(client, chosen: ChosenInlineResult):
    # result_id IS the cache token (see inline_search above) — the whole
    # point of inline feedback: Telegram hands back inline_message_id,
    # which edit_inline_media/edit_inline_text can target directly without
    # the bot ever knowing which chat the result landed in.
    await run_download(client, chosen.result_id, inline_message_id=chosen.inline_message_id)
