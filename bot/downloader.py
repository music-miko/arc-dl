import contextlib
import os
import re
import uuid
from urllib.parse import urlparse

import aiohttp
from pyrogram import Client
from pyrogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo

from .config import config
from .ffmpeg_utils import ensure_mp3
from .utils import duration_to_seconds, guess_kind_from_ext, sanitize_filename

_TELEGRAM_CDN_RE = re.compile(r"https?://(?:t\.me|telegram\.dog)/([^/]+)/(\d+)")


async def _download_http(url: str, dest_path_no_ext: str) -> tuple[str, str]:
    """Downloads url to dest_path_no_ext + detected extension. Returns
    (actual_path, ext)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as r:
            if r.status != 200:
                raise RuntimeError(f"CDN returned HTTP {r.status}")

            ext = ""
            cd = r.headers.get("Content-Disposition")
            if cd:
                m = re.findall(r'filename="?([^";]+)"?', cd)
                if m:
                    ext = os.path.splitext(m[0].split("?")[0])[1]
            if not ext:
                ext = os.path.splitext(urlparse(url).path)[1]
            if not ext:
                ct = (r.headers.get("Content-Type") or "").split(";")[0].strip()
                ext = {
                    "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
                    "video/mp4": ".mp4", "video/webm": ".webm",
                    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                }.get(ct, ".bin")

            dest_path = dest_path_no_ext + ext
            with open(dest_path, "wb") as f:
                async for chunk in r.content.iter_chunked(64 * 1024):
                    if chunk:
                        f.write(chunk)

            return dest_path, ext


async def _download_telegram_cdn(client: Client, cdn_url: str, dest_path_no_ext: str) -> tuple[str, str]:
    m = _TELEGRAM_CDN_RE.match(cdn_url)
    if not m:
        raise RuntimeError(f"Unrecognized Telegram cdn link: {cdn_url}")
    username, message_id = m.group(1), int(m.group(2))

    msg = await client.get_messages(username, message_id)
    if not msg or not (msg.audio or msg.document or msg.voice):
        raise RuntimeError("Cached Telegram message has no downloadable media")

    dest_path = dest_path_no_ext + ".mp3"
    await client.download_media(msg, file_name=dest_path)
    return dest_path, ".mp3"


async def _download_thumbnail(url: str | None, dest_path: str) -> str | None:
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    return None
                with open(dest_path, "wb") as f:
                    f.write(await r.read())
        return dest_path
    except Exception:
        return None


def _build_caption(title: str, artist: str = "") -> str:
    caption = f"🎵 **{title}**" if title else ""
    if artist:
        caption += f"\n👤 {artist}"
    caption += f"\n\n{config.PROMO_TAG}"
    return caption


async def _fetch_and_prepare(
    client: Client,
    cdn_url: str,
    title: str,
    platform: str,
) -> tuple[str, str, str]:
    """Downloads cdn_url, force-converts to mp3 ONLY when platform is
    'youtube' (every other platform is sent exactly as fetched — no
    transcoding). Returns (file_path, ext, kind) where kind is one of
    audio/video/photo/document."""
    job_id = uuid.uuid4().hex[:12]
    raw_base = os.path.join(config.DOWNLOAD_DIR, job_id)

    if _TELEGRAM_CDN_RE.match(cdn_url):
        path, ext = await _download_telegram_cdn(client, cdn_url, raw_base)
    else:
        path, ext = await _download_http(cdn_url, raw_base)

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("Downloaded file is empty")

    if platform == "youtube":
        mp3_path = await ensure_mp3(path)
        if mp3_path != path:
            with contextlib.suppress(Exception):
                os.remove(path)
        safe_name = sanitize_filename(title)
        final_path = os.path.join(config.DOWNLOAD_DIR, f"{job_id}_{safe_name}.mp3")
        os.replace(mp3_path, final_path)
        return final_path, ".mp3", "audio"

    kind = guess_kind_from_ext(ext)
    safe_name = sanitize_filename(title)
    final_path = os.path.join(config.DOWNLOAD_DIR, f"{job_id}_{safe_name}{ext}")
    if os.path.abspath(path) != os.path.abspath(final_path):
        os.replace(path, final_path)
    return final_path, ext, kind


def _cleanup(*paths: str | None) -> None:
    for p in paths:
        if p:
            with contextlib.suppress(Exception):
                if os.path.exists(p):
                    os.remove(p)


async def deliver_to_chat(
    client: Client,
    chat_id: int,
    cdn_url: str,
    title: str,
    artist: str = "",
    duration=None,
    thumbnail_url: str | None = None,
    platform: str = "youtube",
) -> None:
    """Fetches cdn_url and sends it to chat_id, named after the title.
    Raises on failure — callers show the error to the user."""
    thumb_path = os.path.join(config.DOWNLOAD_DIR, f"{uuid.uuid4().hex[:12]}.jpg")
    file_path = None
    try:
        file_path, ext, kind = await _fetch_and_prepare(client, cdn_url, title, platform)
        thumb = await _download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
        caption = _build_caption(title, artist)
        safe_name = sanitize_filename(title) + ext

        if kind == "audio":
            await client.send_audio(
                chat_id, audio=file_path, file_name=safe_name,
                title=title[:60] if title else None,
                performer=artist[:60] if artist else None,
                duration=duration_to_seconds(duration),
                thumb=thumb, caption=caption,
            )
        elif kind == "video":
            await client.send_video(
                chat_id, video=file_path, file_name=safe_name,
                duration=duration_to_seconds(duration),
                thumb=thumb, caption=caption,
            )
        elif kind == "photo":
            await client.send_photo(chat_id, photo=file_path, caption=caption)
        else:
            await client.send_document(chat_id, document=file_path, file_name=safe_name, caption=caption)

    finally:
        _cleanup(file_path, thumb_path)


async def deliver_to_inline(
    client: Client,
    inline_message_id: str,
    cdn_url: str,
    title: str,
    artist: str = "",
    duration=None,
    thumbnail_url: str | None = None,
    platform: str = "youtube",
) -> None:
    """Same as deliver_to_chat, but edits the message that Telegram already
    inserted for the chosen inline result — via inline_message_id, which
    works regardless of which chat it landed in (that's the whole point of
    inline feedback: Telegram itself handles delivery to that message, the
    bot never needs to know the chat)."""
    thumb_path = os.path.join(config.DOWNLOAD_DIR, f"{uuid.uuid4().hex[:12]}.jpg")
    file_path = None
    try:
        file_path, ext, kind = await _fetch_and_prepare(client, cdn_url, title, platform)
        thumb = await _download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
        caption = _build_caption(title, artist)

        if kind == "audio":
            media = InputMediaAudio(
                media=file_path, caption=caption,
                title=title[:60] if title else None,
                performer=artist[:60] if artist else None,
                duration=duration_to_seconds(duration),
                thumb=thumb,
            )
        elif kind == "video":
            media = InputMediaVideo(
                media=file_path, caption=caption,
                duration=duration_to_seconds(duration), thumb=thumb,
            )
        elif kind == "photo":
            media = InputMediaPhoto(media=file_path, caption=caption)
        else:
            media = InputMediaDocument(media=file_path, caption=caption)

        await client.edit_inline_media(inline_message_id, media=media)

    finally:
        _cleanup(file_path, thumb_path)
