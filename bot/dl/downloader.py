# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
import contextlib
import os
import re
import uuid
from urllib.parse import urlparse

import aiohttp
from pyrogram import Client
from pyrogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo

from .. import LOGGER
from ..core.config import config
from ..utils.format import duration_to_seconds, guess_kind_from_ext, sanitize_filename, truncate
from ..utils.keyboards import keyboards
from ..utils.mime import sniffer
from .ffmpeg import ensure_audio

_CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_OK_STATUSES = {200, 206}

_FETCH_RETRIES = 2


class MediaDownloader:
    def __init__(self):
        self.download_dir = "downloads"
        self.fetch_timeout = 300.0
        self.telegram_cdn_re = re.compile(r"https?://(?:t\.me|telegram\.dog)/([^/]+)/(\d+)")
        os.makedirs(self.download_dir, exist_ok=True)

    async def _download_http(self, url: str, dest_path_no_ext: str) -> tuple[str, str]:
        last_error: Exception | None = None

        for attempt in range(1, _FETCH_RETRIES + 1):
            try:
                return await self._download_http_once(url, dest_path_no_ext)
            except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < _FETCH_RETRIES:
                    LOGGER.warning("CDN fetch failed (attempt %d/%d): %s — retrying", attempt, _FETCH_RETRIES, e)
                    await asyncio.sleep(1.5)

        raise RuntimeError(f"CDN fetch failed after {_FETCH_RETRIES} attempts: {last_error}")

    async def _download_http_once(self, url: str, dest_path_no_ext: str) -> tuple[str, str]:
        timeout = aiohttp.ClientTimeout(total=self.fetch_timeout)
        async with aiohttp.ClientSession(headers=_CDN_HEADERS) as session:
            async with session.get(url, timeout=timeout) as r:
                if r.status not in _OK_STATUSES:
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
                size = 0
                with open(dest_path, "wb") as f:
                    async for chunk in r.content.iter_chunked(64 * 1024):
                        if chunk:
                            size += len(chunk)
                            f.write(chunk)

                if size == 0:
                    with contextlib.suppress(Exception):
                        os.remove(dest_path)
                    raise RuntimeError("CDN response body was empty")

                return dest_path, ext

    async def _download_telegram_cdn(self, client: Client, cdn_url: str, dest_path_no_ext: str) -> tuple[str, str]:
        m = self.telegram_cdn_re.match(cdn_url)
        if not m:
            raise RuntimeError(f"Unrecognized Telegram cdn link: {cdn_url}")
        username, message_id = m.group(1), int(m.group(2))

        msg = await client.get_messages(username, message_id)
        media = msg and (msg.audio or msg.document or msg.voice)
        if not media:
            raise RuntimeError("Cached Telegram message has no downloadable media")

        ext = self._extension_from_media(msg, media)
        dest_path = dest_path_no_ext + ext
        await client.download_media(msg, file_name=dest_path)
        return dest_path, ext

    def _extension_from_media(self, msg, media) -> str:
        if msg.voice:
            return ".ogg"
        file_name = getattr(media, "file_name", None)
        if file_name and "." in file_name:
            return os.path.splitext(file_name)[1]
        mime_type = getattr(media, "mime_type", None) or ""
        for ext, mime in sniffer.ext_mime.items():
            if mime == mime_type:
                return ext
        return ".bin"

    async def _download_thumbnail(self, url: str | None, dest_path: str) -> str | None:
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

    def _build_caption(self, title: str, artist: str = "") -> str:
        caption = title or ""
        if artist:
            caption += f"\n{artist}"
        caption += f"\n\n@{keyboards.channel_username}"
        return caption

    async def _fetch_and_prepare(
        self, client: Client, cdn_url: str, title: str, platform: str,
    ) -> tuple[str, str, str]:
        job_id = uuid.uuid4().hex[:12]
        raw_base = os.path.join(self.download_dir, job_id)

        if self.telegram_cdn_re.match(cdn_url):
            path, ext = await self._download_telegram_cdn(client, cdn_url, raw_base)
        else:
            path, ext = await self._download_http(cdn_url, raw_base)

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise RuntimeError("Downloaded file is empty")

        if platform == "youtube":
            audio_path, audio_ext = await ensure_audio(path)
            if audio_path != path:
                with contextlib.suppress(Exception):
                    os.remove(path)
            safe_name = sanitize_filename(title)
            final_path = os.path.join(self.download_dir, f"{job_id}_{safe_name}{audio_ext}")
            os.replace(audio_path, final_path)
            return final_path, audio_ext, "audio"

        kind = guess_kind_from_ext(ext)
        if kind == "document":
            sniffed = sniffer.sniff_file(path)
            if sniffed:
                kind = sniffed
                ext = ".jpg" if sniffed == "photo" else ".mp4"

        safe_name = sanitize_filename(title)
        final_path = os.path.join(self.download_dir, f"{job_id}_{safe_name}{ext}")
        if os.path.abspath(path) != os.path.abspath(final_path):
            os.replace(path, final_path)
        return final_path, ext, kind

    def _cleanup(self, *paths: str | None) -> None:
        for p in paths:
            if p:
                with contextlib.suppress(Exception):
                    if os.path.exists(p):
                        os.remove(p)

    async def deliver_to_chat(
        self,
        client: Client,
        chat_id: int,
        cdn_url: str,
        title: str,
        artist: str = "",
        duration=None,
        thumbnail_url: str | None = None,
        platform: str = "youtube",
    ) -> None:
        thumb_path = os.path.join(self.download_dir, f"{uuid.uuid4().hex[:12]}.jpg")
        file_path = None
        try:
            file_path, ext, kind = await self._fetch_and_prepare(client, cdn_url, title, platform)
            thumb = await self._download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
            caption = self._build_caption(title, artist)
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
            self._cleanup(file_path, thumb_path)

    async def deliver_inline(
        self,
        client: Client,
        inline_message_id: str,
        cdn_url: str,
        title: str,
        artist: str = "",
        duration=None,
        thumbnail_url: str | None = None,
        platform: str = "youtube",
    ) -> None:
        relay_chat = config.log_channel
        if not relay_chat:
            raise RuntimeError("LOG_CHANNEL is not configured — required to deliver inline results")

        thumb_path = os.path.join(self.download_dir, f"{uuid.uuid4().hex[:12]}.jpg")
        file_path = None
        try:
            file_path, ext, kind = await self._fetch_and_prepare(client, cdn_url, title, platform)
            thumb = await self._download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
            caption = self._build_caption(title, artist)
            safe_name = sanitize_filename(title) + ext

            if kind == "audio":
                relay_msg = await client.send_audio(
                    relay_chat, audio=file_path, file_name=safe_name,
                    title=title[:60] if title else None,
                    performer=artist[:60] if artist else None,
                    duration=duration_to_seconds(duration),
                    thumb=thumb, caption=caption,
                )
                media = InputMediaAudio(
                    media=relay_msg.audio.file_id,
                    caption=caption,
                    title=truncate(title, 60) if title else None,
                    performer=truncate(artist, 60) if artist else "",
                    duration=duration_to_seconds(duration),
                )
            elif kind == "video":
                relay_msg = await client.send_video(
                    relay_chat, video=file_path, file_name=safe_name,
                    duration=duration_to_seconds(duration),
                    thumb=thumb, caption=caption,
                )
                media = InputMediaVideo(
                    media=relay_msg.video.file_id, caption=caption, duration=duration_to_seconds(duration),
                )
            elif kind == "photo":
                relay_msg = await client.send_photo(relay_chat, photo=file_path, caption=caption)
                media = InputMediaPhoto(media=relay_msg.photo.file_id, caption=caption)
            else:
                relay_msg = await client.send_document(
                    relay_chat, document=file_path, file_name=safe_name, caption=caption,
                )
                media = InputMediaDocument(media=relay_msg.document.file_id, caption=caption)

            await client.edit_inline_media(inline_message_id, media=media)

        finally:
            self._cleanup(file_path, thumb_path)


downloader = MediaDownloader()
