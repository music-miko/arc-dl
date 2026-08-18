# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from .. import LOGGER
from ..core.client import app
from ..core.mongo import mongo
from ..dl.actions import run_download
from ..dl.api_client import YTAPIError, yt_api
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.keyboards import keyboards
from ..utils.texts import NO_RESULTS_TEXT, STARTING_TEXT, UNSUPPORTED_LINK_TEXT

not_command_filter = filters.create(lambda _, __, m: not (m.text or "").startswith("/"))


async def _start_single_download(client, message: Message, entry: dict) -> None:
    token = cache.put_new(entry)
    status = await message.reply_text(STARTING_TEXT)
    await run_download(client, token, chat_id=message.chat.id, status=status)


async def _show_paginated_list(message: Message, header: str, tracks: list[dict], entry_builder) -> None:
    entries = []
    for t in tracks:
        built = entry_builder(t)
        token = cache.put_new(built)
        entries.append((token, {"title": built.get("title"), "duration": t.get("duration")}))

    if not entries:
        await message.reply_text(NO_RESULTS_TEXT)
        return

    list_token = cache.put_new({"entries": entries})
    await message.reply_text(
        header, reply_markup=keyboards.paginated_results_keyboard(list_token, entries, page=0)
    )


async def handle_text(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    kind, value = classifier.classify(message.text)

    try:
        if kind == "youtube_video":
            title, channel, duration, thumb = "YouTube Audio", "", None, None
            try:
                hits = await yt_api.search_youtube(value, limit=1)
                if hits:
                    h = hits[0]
                    title, channel, duration, thumb = h["title"], h.get("channel", ""), h.get("duration"), h.get("thumbnail")
            except YTAPIError:
                pass

            await _start_single_download(client, message, {
                "type": "youtube", "video_id": value,
                "title": title, "artist": channel, "duration": duration, "thumbnail": thumb,
            })

        elif kind == "youtube_playlist":
            data = await yt_api.get_youtube_playlist(value)
            tracks = data.get("tracks", [])
            await _show_paginated_list(
                message, f"Playlist - {len(tracks)} tracks. Tap to download:",
                tracks,
                lambda t: {
                    "type": "youtube", "video_id": t.get("url"),
                    "title": t.get("title"), "artist": t.get("channel"),
                    "duration": t.get("duration"), "thumbnail": t.get("thumbnail"),
                },
            )

        elif kind == "spotify_track":
            await _start_single_download(client, message, {
                "type": "spotify", "url": value, "title": "Spotify Track",
            })

        elif kind == "spotify_playlist":
            data = await yt_api.get_spotify_playlist(value)
            tracks = data.get("tracks", [])
            await _show_paginated_list(
                message, f"Playlist - {len(tracks)} tracks. Tap to download:",
                tracks,
                lambda t: {"type": "spotify", "url": t.get("url"), "title": t.get("name"), "duration": t.get("duration")},
            )

        elif kind == "soundcloud":
            result = await yt_api.download_soundcloud(value)
            if not result or not result.get("cdn"):
                await message.reply_text("Couldn't fetch that SoundCloud track.")
                return
            await _start_single_download(client, message, {
                "type": "soundcloud_direct", "cdn": result["cdn"],
                "title": result.get("title") or result.get("name") or "SoundCloud Track",
                "artist": result.get("artist") or "",
                "duration": result.get("duration"),
                "thumbnail": result.get("thumbnail") or result.get("thumbnail_url"),
            })

        elif kind in yt_api.social_platforms:
            await _start_single_download(client, message, {
                "type": kind, "url": value, "title": kind.capitalize(),
            })

        elif kind == "unsupported_url":
            await message.reply_text(UNSUPPORTED_LINK_TEXT)

        else:
            results = await yt_api.search_youtube(value, limit=5)
            entries = []
            for r in results:
                token = cache.put_new({
                    "type": "youtube", "video_id": r["video_id"],
                    "title": r["title"], "artist": r.get("channel", ""),
                    "duration": r.get("duration"), "thumbnail": r.get("thumbnail"),
                })
                entries.append((token, {"title": r["title"], "duration": r.get("duration")}))

            if not entries:
                await message.reply_text(NO_RESULTS_TEXT)
                return

            await message.reply_text(
                f"Top results for {value}:", reply_markup=keyboards.results_keyboard(entries)
            )

    except YTAPIError as e:
        await message.reply_text(str(e))
    except Exception as e:
        LOGGER.exception("Unexpected error handling message from %s", message.chat.id)
        await message.reply_text(f"Something went wrong: {e}")


HANDLERS = [
    (MessageHandler, handle_text, filters.private & filters.text & ~filters.via_bot & not_command_filter),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
