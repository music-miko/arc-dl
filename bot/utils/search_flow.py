# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.enums import ChatType
from pyrogram.types import Message

from ..dl.actions import run_download
from ..dl.api_client import YTAPIError, yt_api
from ..dl.terabox_flow import terabox_flow
from ..locale import text as t
from .buttons import keyboards
from .helper import cache


async def start_single_download(client, message: Message, entry: dict, lang: str) -> None:
    token = cache.put_new(entry)
    status = await message.reply_text(t("starting_text", lang))
    await run_download(client, token, chat_id=message.chat.id, status=status, lang=lang)


async def show_paginated_list(
    message: Message, header: str, tracks: list[dict], entry_builder, lang: str
) -> None:
    entries = []
    for tr in tracks:
        built = entry_builder(tr)
        token = cache.put_new(built)
        entries.append((token, {"title": built.get("title"), "duration": tr.get("duration")}))

    if not entries:
        await message.reply_text(t("no_results_text", lang))
        return

    list_token = cache.put_new({"entries": entries})
    await message.reply_text(
        header, reply_markup=keyboards.paginated_results_keyboard(list_token, entries, page=0, lang=lang)
    )


async def dispatch_query(client, message: Message, kind: str, value: str, lang: str) -> None:
    if kind == "youtube_video":
        title, channel, duration, thumb = "YouTube Audio", "", None, None
        try:
            hits = await yt_api.search_youtube(value, limit=1)
            if hits:
                h = hits[0]
                title, channel, duration, thumb = h["title"], h.get("channel", ""), h.get("duration"), h.get("thumbnail")
        except YTAPIError:
            pass

        await start_single_download(client, message, {
            "type": "youtube", "video_id": value,
            "title": title, "artist": channel, "duration": duration, "thumbnail": thumb,
        }, lang)

    elif kind == "youtube_playlist":
        data = await yt_api.get_youtube_playlist(value)
        tracks = data.get("tracks", [])
        await show_paginated_list(
            message, t("playlist_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "youtube", "video_id": tr.get("url"),
                "title": tr.get("title"), "artist": tr.get("channel"),
                "duration": tr.get("duration"), "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "spotify_track":
        await start_single_download(client, message, {
            "type": "spotify", "url": value, "title": "Spotify Track",
        }, lang)

    elif kind == "spotify_playlist":
        data = await yt_api.get_spotify_playlist(value)
        tracks = data.get("tracks", [])
        await show_paginated_list(
            message, t("playlist_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {"type": "spotify", "url": tr.get("url"), "title": tr.get("name"), "duration": tr.get("duration")},
            lang,
        )

    elif kind == "soundcloud":
        result = await yt_api.download_soundcloud(value)
        if not result or not result.get("cdn"):
            await message.reply_text(t("soundcloud_fetch_failed_text", lang))
            return
        await start_single_download(client, message, {
            "type": "soundcloud_direct", "cdn": result["cdn"],
            "title": result.get("title") or result.get("name") or "SoundCloud Track",
            "artist": result.get("artist") or "",
            "duration": result.get("duration"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url"),
        }, lang)

    elif kind in yt_api.social_platforms:
        await start_single_download(client, message, {
            "type": kind, "url": value, "title": kind.capitalize(),
        }, lang)

    elif kind == "applemusic_track":
        await start_single_download(client, message, {
            "type": "applemusic", "url": value, "title": "Apple Music Track",
        }, lang)

    elif kind == "applemusic_playlist":
        data = await yt_api.search_applemusic(value)
        tracks = (data or {}).get("tracks", [])
        await show_paginated_list(
            message, t("applemusic_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "applemusic", "url": tr.get("track_url"),
                "title": tr.get("title"), "artist": tr.get("artist"),
                "duration": tr.get("duration"), "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "jiosaavn_track":
        await start_single_download(client, message, {
            "type": "jiosaavn", "url": value, "title": "JioSaavn Track",
        }, lang)

    elif kind == "jiosaavn_playlist":
        data = await yt_api.search_jiosaavn(value)
        tracks = (data or {}).get("tracks", [])
        await show_paginated_list(
            message, t("jiosaavn_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "jiosaavn", "url": tr.get("song_url"),
                "title": tr.get("title"), "duration": tr.get("duration"),
                "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "terabox":
        if message.chat.type != ChatType.PRIVATE:
            await message.reply_text(t("terabox_private_only_text", lang))
            return
        status = await message.reply_text(t("starting_text", lang))
        await terabox_flow.run(client, value, chat_id=message.chat.id, status=status, lang=lang)

    elif kind == "unsupported_url":
        await message.reply_text(t("unsupported_link_text", lang))

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
            await message.reply_text(t("no_results_text", lang))
            return

        await message.reply_text(
            t("top_results_text", lang, query=value), reply_markup=keyboards.results_keyboard(entries, lang=lang)
        )
