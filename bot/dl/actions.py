# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import contextlib
import os
import uuid

from pyrogram import Client
from pyrogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo

from .. import LOGGER
from ..utils.cache import cache
from ..utils.classifier import classifier
from ..utils.format import duration_to_seconds, guess_kind_from_ext, truncate
from ..utils.mime import sniffer
from ..utils.texts import DOWNLOADING_TEXT, EXPIRED_TEXT, SENDING_TEXT
from .api_client import YTAPIError, yt_api
from .downloader import downloader

_PROBE_HEADERS = {"Accept": "*/*"}


async def resolve_cdn(entry: dict) -> tuple[str, dict]:
    if entry.get("cdn"):
        return entry["cdn"], entry

    kind = entry["type"]

    if kind == "youtube":
        result = await yt_api.download_youtube(entry["video_id"], is_video=False)
        return result.get("cdn"), entry

    if kind == "spotify":
        result = await yt_api.download_spotify(entry["url"])
        entry = {
            **entry,
            "title": result.get("song_name") or entry.get("title"),
            "thumbnail": result.get("thumbnail_url") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result.get("cdn"), entry

    if kind in yt_api.social_platforms:
        method = getattr(yt_api, yt_api.social_platforms[kind])
        result = await method(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"{kind.capitalize()} fetch failed")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url") or entry.get("thumbnail"),
        }
        return result.get("cdn"), entry

    if kind == "soundcloud_direct_link":
        result = await yt_api.download_soundcloud(entry["url"])
        if not result or not result.get("cdn"):
            raise YTAPIError("SoundCloud fetch failed")
        entry = {
            **entry,
            "title": result.get("title") or result.get("name") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result["cdn"], entry

    raise YTAPIError(f"Unknown result type: {kind!r}")


async def run_download(client: Client, token: str, *, chat_id: int, status=None) -> None:
    entry = cache.get(token)
    if not entry:
        await _update_status(status, EXPIRED_TEXT)
        return

    platform = entry["type"]
    if platform in ("soundcloud_direct", "soundcloud_direct_link"):
        platform = "soundcloud"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    duration = entry.get("duration")
    thumbnail = entry.get("thumbnail")

    if platform in classifier.social_labels and title == "Untitled":
        title = classifier.social_labels[platform]

    await _update_status(status, f"{DOWNLOADING_TEXT} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        thumbnail = entry.get("thumbnail") or thumbnail
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await _update_status(status, f"{SENDING_TEXT} {title}")

        await downloader.deliver_to_chat(
            client, chat_id, cdn_url,
            title=title, artist=artist, duration=duration,
            thumbnail_url=thumbnail, platform=platform,
        )
        if status:
            await status.delete()

    except YTAPIError as e:
        LOGGER.warning("Download failed for token=%s: %s", token, e)
        await _update_status(status, f"Failed: {e}")
    except Exception as e:
        LOGGER.exception("Unexpected error delivering token=%s", token)
        await _update_status(status, f"Something went wrong: {e}")


async def run_inline_download(client: Client, token: str, callback_query) -> None:
    """Deliver a download triggered from an inline result.

    Inline-sent messages have no chat_id/message_id the bot can post into
    (the bot usually isn't even a member of that chat), only an
    inline_message_id. So instead of sending a new message we edit the
    placeholder message's media in place once the file/link is ready.
    """
    entry = cache.get(token)
    if not entry:
        await _safe_edit_inline(callback_query, EXPIRED_TEXT)
        return

    platform = entry["type"]
    if platform in ("soundcloud_direct", "soundcloud_direct_link"):
        platform = "soundcloud"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    duration = entry.get("duration")

    if platform in classifier.social_labels and title == "Untitled":
        title = classifier.social_labels[platform]

    await _safe_edit_inline(callback_query, f"{DOWNLOADING_TEXT} {title}")

    local_path = None
    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await _safe_edit_inline(callback_query, f"{SENDING_TEXT} {title}")

        caption = title
        if artist:
            caption += f"\n{artist}"

        if downloader.telegram_cdn_re.match(cdn_url):
            job_id = uuid.uuid4().hex[:12]
            base_path = os.path.join(downloader.download_dir, job_id)
            local_path, ext = await downloader._download_telegram_cdn(client, cdn_url, base_path)
            media_source = local_path
            kind = guess_kind_from_ext(ext)
        else:
            media_source = cdn_url
            kind, _ct = await sniffer.probe_remote(cdn_url, _PROBE_HEADERS)
            if kind is None:
                kind = "audio" if platform in ("youtube", "spotify", "soundcloud") else "document"

        if kind == "audio":
            media = InputMediaAudio(
                media=media_source,
                caption=caption,
                title=truncate(title, 60) if title else None,
                performer=truncate(artist, 60) if artist else "",
                duration=duration_to_seconds(duration),
            )
        elif kind == "video":
            media = InputMediaVideo(
                media=media_source, caption=caption, duration=duration_to_seconds(duration),
            )
        elif kind == "photo":
            media = InputMediaPhoto(media=media_source, caption=caption)
        else:
            media = InputMediaDocument(media=media_source, caption=caption)

        await callback_query.edit_message_media(media=media)

    except YTAPIError as e:
        LOGGER.warning("Inline download failed for token=%s: %s", token, e)
        await _safe_edit_inline(callback_query, f"Failed: {e}")
    except Exception as e:
        LOGGER.exception("Unexpected error delivering inline token=%s", token)
        await _safe_edit_inline(callback_query, f"Something went wrong: {e}")
    finally:
        if local_path:
            with contextlib.suppress(Exception):
                if os.path.exists(local_path):
                    os.remove(local_path)


async def _safe_edit_inline(callback_query, text: str) -> None:
    try:
        await callback_query.edit_message_text(text)
    except Exception:
        pass


async def _update_status(status, text: str) -> None:
    if not status:
        return
    try:
        await status.edit_text(text)
    except Exception:
        pass
