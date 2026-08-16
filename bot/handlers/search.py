from pyrogram import filters
from pyrogram.types import Message

from bot import cache
from bot.actions import run_download
from bot.api_client import SOCIAL_DOWNLOAD_METHODS, YTAPIError, yt_api
from bot.client import app
from bot.database import touch_user
from bot.keyboards import paginated_results_keyboard, results_keyboard
from bot.utils import classify_message

_SOCIAL_LABELS = {
    "instagram": "📸 Instagram", "facebook": "📘 Facebook", "threads": "🧵 Threads",
    "bluesky": "🦋 Bluesky", "tiktok": "🎵 TikTok", "twitter": "🐦 Twitter / X",
}


async def _start_single_download(client, message: Message, entry: dict) -> None:
    """For links that point at exactly one track/post — goes through the
    same cache + run_download path as button clicks, just skipping the button."""
    token = cache.put_new(entry)
    status = await message.reply_text(f"⏳ Fetching **{entry.get('title') or 'media'}**…")
    await run_download(client, token, chat_id=message.chat.id, status=status)


async def _show_paginated_list(message: Message, header: str, tracks: list[dict], entry_builder) -> None:
    """Shows every track (not just the first N) behind real Prev/Next
    pagination — picking a track downloads just that one, never the whole
    playlist."""
    entries = []
    for t in tracks:
        built = entry_builder(t)
        token = cache.put_new(built)
        entries.append((token, {"title": built.get("title"), "duration": t.get("duration")}))

    if not entries:
        await message.reply_text("😕 No tracks found.")
        return

    list_token = cache.put_new({"entries": entries})
    await message.reply_text(
        header, reply_markup=paginated_results_keyboard(list_token, entries, page=0)
    )


@app.on_message(filters.private & filters.text & ~filters.via_bot)
async def handle_text(client, message: Message):
    if message.text.startswith("/"):
        return  # let dedicated command handlers deal with it

    user = message.from_user
    if user:
        await touch_user(user.id, user.first_name or "", user.username)

    kind, value = classify_message(message.text)

    try:
        if kind == "youtube_video":
            # download_youtube() extracts the video id server-side, so a
            # raw URL or bare ID both work without extra parsing here.
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
                message, f"📻 **Playlist** — {len(tracks)} tracks. Tap to download:",
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
                message, f"📻 **Playlist** — {len(tracks)} tracks. Tap to download:",
                tracks,
                lambda t: {"type": "spotify", "url": t.get("url"), "title": t.get("name"), "duration": t.get("duration")},
            )

        elif kind == "soundcloud":
            result = await yt_api.download_soundcloud(value)
            if not result or not result.get("cdn"):
                await message.reply_text("❌ Couldn't fetch that SoundCloud track.")
                return
            await _start_single_download(client, message, {
                "type": "soundcloud_direct", "cdn": result["cdn"],
                "title": result.get("title") or result.get("name") or "SoundCloud Track",
                "artist": result.get("artist") or "",
                "duration": result.get("duration"),
                "thumbnail": result.get("thumbnail") or result.get("thumbnail_url"),
            })

        elif kind in SOCIAL_DOWNLOAD_METHODS:
            await _start_single_download(client, message, {
                "type": kind, "url": value, "title": _SOCIAL_LABELS.get(kind, kind.capitalize()),
            })

        elif kind == "unsupported_url":
            await message.reply_text(
                "🤔 I don't recognize that link. I support YouTube, Spotify, SoundCloud, "
                "Instagram, Facebook, Threads, Bluesky, TikTok and Twitter/X links, "
                "or just send me a song name."
            )

        else:  # plain-text search
            results = await yt_api.search_youtube(value, limit=5)
            entries = []
            for r in results:
                token = cache.put_new({
                    "type": "youtube", "video_id": r["video_id"],
                    "title": r["title"], "artist": r.get("channel", ""),
                    "duration": r.get("duration"), "thumbnail": r.get("thumbnail"),
                })
                entries.append((token, {"title": r["title"], "duration": r.get("duration")}))

            await message.reply_text(
                f"🔍 Top results for **{value}**:", reply_markup=results_keyboard(entries)
            )

    except YTAPIError as e:
        await message.reply_text(f"❌ {e}")
    except Exception as e:
        await message.reply_text(f"❌ Something went wrong: {e}")
