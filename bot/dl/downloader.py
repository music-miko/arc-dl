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
from pyrogram.errors import RPCError
from pyrogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo

from .. import LOGGER
from ..locale import default_lang
from ..utils.buttons import keyboards
from ..utils.helper import duration_to_seconds, guess_kind_from_ext, sanitize_filename
from .ffmpeg import ensure_audio, probe_video_meta


class MediaSniffer:
    def __init__(self):
        self.probe_timeout = aiohttp.ClientTimeout(total=10)
        self.ext_mime = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".m4a": "audio/mp4",
            ".mp3": "audio/mpeg",
        }

    def sniff_bytes(self, head: bytes) -> str | None:
        if head[:3] == b"\xff\xd8\xff":
            return "photo"
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return "photo"
        if head[:6] in (b"GIF87a", b"GIF89a"):
            return "photo"
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return "photo"
        if head[4:8] == b"ftyp":
            return "video"
        if head[:4] == b"\x1aE\xdf\xa3":
            return "video"
        return None

    def sniff_file(self, path: str) -> str | None:
        try:
            with open(path, "rb") as f:
                return self.sniff_bytes(f.read(64))
        except OSError:
            return None

    def mime_for_ext(self, ext: str, default: str = "video/mp4") -> str:
        return self.ext_mime.get(ext.lower(), default)

    async def probe_remote(self, url: str, headers: dict) -> tuple[str | None, str | None]:
        content_type = await self._head_content_type(url, headers)
        if not content_type:
            content_type = await self._ranged_content_type(url, headers)

        if not content_type:
            return None, None

        main_type = content_type.split(";")[0].strip().lower()
        if main_type.startswith("audio/"):
            return "audio", main_type
        if main_type.startswith("video/"):
            return "video", main_type
        if main_type.startswith("image/"):
            return "photo", main_type
        return None, main_type

    async def _head_content_type(self, url: str, headers: dict) -> str | None:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.head(url, timeout=self.probe_timeout, allow_redirects=True) as r:
                    if r.status < 400:
                        return r.headers.get("Content-Type")
        except Exception:
            pass
        return None

    async def _ranged_content_type(self, url: str, headers: dict) -> str | None:
        range_headers = {**headers, "Range": "bytes=0-64"}
        try:
            async with aiohttp.ClientSession(headers=range_headers) as session:
                async with session.get(url, timeout=self.probe_timeout) as r:
                    if r.status < 400:
                        return r.headers.get("Content-Type")
        except Exception:
            pass
        return None


sniffer = MediaSniffer()


class MediaDownloader:
    def __init__(self):
        self.download_dir = "downloads"
        self.fetch_timeout = 300.0
        self.fetch_retries = 2
        self.ok_statuses = {200, 206}
        self.max_group_size = 10
        self.cdn_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }
        self.telegram_cdn_re = re.compile(
            r"https?://(?:t\.me|telegram\.dog)/(?P<uname>[A-Za-z0-9_]+)/(?P<mid>\d+)"
        )
        self.telegram_media_kinds: tuple[tuple[str, str], ...] = (
            ("audio", "audio"),
            ("voice", "audio"),
            ("video", "video"),
            ("animation", "video"),
            ("photo", "photo"),
            ("video_note", "video"),
            ("document", "document"),
            ("sticker", "document"),
        )
        os.makedirs(self.download_dir, exist_ok=True)

    async def _download_http(
        self, url: str, dest_path_no_ext: str, filename_hint: str | None = None
    ) -> tuple[str, str]:
        last_error: Exception | None = None

        for attempt in range(1, self.fetch_retries + 1):
            try:
                return await self._download_http_once(url, dest_path_no_ext, filename_hint)
            except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self.fetch_retries:
                    LOGGER.warning(
                        "CDN fetch failed (attempt %d/%d): %s: %s — retrying",
                        attempt, self.fetch_retries, type(e).__name__, e,
                    )
                    await asyncio.sleep(1.5)

        raise RuntimeError(f"CDN fetch failed after {self.fetch_retries} attempts: {type(last_error).__name__}: {last_error}")

    async def _download_http_once(
        self, url: str, dest_path_no_ext: str, filename_hint: str | None = None
    ) -> tuple[str, str]:
        timeout = aiohttp.ClientTimeout(total=self.fetch_timeout)
        async with aiohttp.ClientSession(headers=self.cdn_headers) as session:
            async with session.get(url, timeout=timeout) as r:
                if r.status not in self.ok_statuses:
                    raise RuntimeError(f"CDN returned HTTP {r.status}")

                ext = os.path.splitext(filename_hint)[1] if filename_hint else ""
                cd = r.headers.get("Content-Disposition")
                if not ext and cd:
                    m = re.findall(r'filename="?([^";]+)"?', cd)
                    if m:
                        ext = os.path.splitext(m[0].split("?")[0])[1]
                if not ext:
                    ext = os.path.splitext(urlparse(url).path)[1]
                if not ext:
                    ct = (r.headers.get("Content-Type") or "").split(";")[0].strip()
                    ext = {
                        "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
                        "video/mp4": ".mp4", "video/webm": ".webm", "video/x-matroska": ".mkv",
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

    def _detect_message_media(self, msg) -> tuple[object | None, str | None]:
        if not msg:
            return None, None
        for attr, kind in self.telegram_media_kinds:
            media = getattr(msg, attr, None)
            if media:
                return media, kind
        return None, None

    def _resolve_telegram_link(self, cdn_url: str) -> tuple[str, int] | None:
        m = self.telegram_cdn_re.match(cdn_url)
        if not m:
            return None
        return m.group("uname"), int(m.group("mid"))

    async def _download_telegram_cdn(self, client: Client, cdn_url: str, dest_path_no_ext: str) -> tuple[str, str, str]:
        resolved = self._resolve_telegram_link(cdn_url)
        if not resolved:
            raise RuntimeError(f"Unrecognized Telegram cdn link: {cdn_url}")
        username, message_id = resolved

        try:
            msg = await client.get_messages(username, message_id)
        except RPCError as e:
            raise RuntimeError(f"Couldn't access the cached Telegram file: {e}") from e

        media, kind = self._detect_message_media(msg)
        if not media:
            raise RuntimeError("Cached Telegram message has no downloadable media")

        ext = self._extension_from_media(msg, media, kind)
        dest_path = dest_path_no_ext + ext
        await client.download_media(msg, file_name=dest_path)
        return dest_path, ext, kind

    def _extension_from_media(self, msg, media, kind: str) -> str:
        if msg.voice:
            return ".ogg"
        file_name = getattr(media, "file_name", None)
        if file_name and "." in file_name:
            return os.path.splitext(file_name)[1]
        mime_type = getattr(media, "mime_type", None) or ""
        for ext, mime in sniffer.ext_mime.items():
            if mime == mime_type:
                return ext
        return {"photo": ".jpg", "video": ".mp4", "audio": ".mp3"}.get(kind, ".bin")

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
        caption += "\n\n@ArcUpdates"
        return caption

    async def _fetch_and_prepare(
        self, client: Client, cdn_url: str, platform: str, filename_hint: str | None = None,
    ) -> tuple[str, str, str, int, int, int]:
        job_id = uuid.uuid4().hex[:12]
        raw_base = os.path.join(self.download_dir, job_id)

        known_kind: str | None = None
        if self.telegram_cdn_re.match(cdn_url):
            path, ext, known_kind = await self._download_telegram_cdn(client, cdn_url, raw_base)
        else:
            path, ext = await self._download_http(cdn_url, raw_base, filename_hint)

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise RuntimeError("Downloaded file is empty")

        if platform == "youtube":
            audio_path, audio_ext = await ensure_audio(path)
            if audio_path != path:
                with contextlib.suppress(Exception):
                    os.remove(path)
            final_path = os.path.join(self.download_dir, f"{job_id}{audio_ext}")
            os.replace(audio_path, final_path)
            return final_path, audio_ext, "audio", 0, 0, 0

        kind = known_kind or guess_kind_from_ext(ext)
        if kind == "document":
            sniffed = sniffer.sniff_file(path)
            if sniffed:
                kind = sniffed
                ext = ".jpg" if sniffed == "photo" else ".mp4"

        final_path = os.path.join(self.download_dir, f"{job_id}{ext}")
        if os.path.abspath(path) != os.path.abspath(final_path):
            os.replace(path, final_path)

        width = height = probed_duration = 0
        if kind == "video":
            width, height, probed_duration = await probe_video_meta(final_path)

        return final_path, ext, kind, width, height, probed_duration

    def _cleanup(self, *paths: str | None) -> None:
        for p in paths:
            if p:
                with contextlib.suppress(Exception):
                    if os.path.exists(p):
                        os.remove(p)

    async def _prepare_upload(
        self,
        client: Client,
        cdn_url: str,
        title: str,
        artist: str,
        duration,
        thumbnail_url: str | None,
        platform: str,
        filename_hint: str | None = None,
    ) -> tuple[str, str | None, str, str, int, int, int, str, str]:
        thumb_path = os.path.join(self.download_dir, f"{uuid.uuid4().hex[:12]}.jpg")
        file_path, ext, kind, width, height, probed_duration = await self._fetch_and_prepare(
            client, cdn_url, platform, filename_hint
        )
        thumb = await self._download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
        caption = self._build_caption(title, artist)
        safe_name = sanitize_filename(title) + ext
        resolved_duration = duration_to_seconds(duration) or probed_duration
        return file_path, thumb, thumb_path, kind, width, height, resolved_duration, caption, safe_name

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
        filename_hint: str | None = None,
        lang: str = default_lang,
    ):
        file_path = thumb_path = None
        try:
            file_path, thumb, thumb_path, kind, width, height, resolved_duration, caption, safe_name = (
                await self._prepare_upload(
                    client, cdn_url, title, artist, duration, thumbnail_url, platform, filename_hint
                )
            )

            if kind == "audio":
                sent = await client.send_audio(
                    chat_id, audio=file_path, file_name=safe_name,
                    title=title[:60] if title else None,
                    performer=artist[:60] if artist else None,
                    duration=resolved_duration,
                    thumb=thumb, caption=caption,
                    reply_markup=keyboards.updates_channel_markup(lang),
                )
            elif kind == "video":
                sent = await client.send_video(
                    chat_id, video=file_path, file_name=safe_name,
                    duration=resolved_duration,
                    width=width, height=height,
                    supports_streaming=True,
                    thumb=thumb, caption=caption,
                    reply_markup=keyboards.updates_channel_markup(lang),
                )
            elif kind == "photo":
                sent = await client.send_photo(
                    chat_id, photo=file_path, caption=caption, reply_markup=keyboards.updates_channel_markup(lang),
                )
            else:
                sent = await client.send_document(
                    chat_id, document=file_path, file_name=safe_name, caption=caption,
                    reply_markup=keyboards.updates_channel_markup(lang),
                )

            return sent

        finally:
            self._cleanup(file_path, thumb_path)

    async def deliver_media_group_to_chat(
        self,
        client: Client,
        chat_id: int,
        media_items: list[dict],
        caption: str = "",
        platform: str = "instagram",
    ):
        items = media_items[:self.max_group_size]

        downloaded_paths: list[str] = []
        media_input = []
        try:
            for i, item in enumerate(items):
                item_url = item.get("url")
                if not item_url:
                    continue
                job_id = uuid.uuid4().hex[:12]
                dest_base = os.path.join(self.download_dir, f"{platform}_{job_id}")
                try:
                    path, _ext = await self._download_http(item_url, dest_base)
                except Exception as e:
                    LOGGER.warning("Skipping one media-group item (fetch failed): %s", e)
                    continue

                downloaded_paths.append(path)
                item_caption = caption if i == 0 else None
                item_kind = (item.get("type") or "").lower()
                if item_kind == "video" or path.lower().endswith((".mp4", ".mov", ".webm")):
                    media_input.append(InputMediaVideo(path, caption=item_caption))
                else:
                    media_input.append(InputMediaPhoto(path, caption=item_caption))

            if not media_input:
                raise RuntimeError("None of the media-group items could be fetched")

            return await client.send_media_group(chat_id, media_input)

        finally:
            self._cleanup(*downloaded_paths)

    async def deliver_to_inline(
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
        file_path = thumb_path = None
        try:
            file_path, thumb, thumb_path, kind, width, height, resolved_duration, caption, safe_name = (
                await self._prepare_upload(client, cdn_url, title, artist, duration, thumbnail_url, platform)
            )

            if kind == "audio":
                media = InputMediaAudio(
                    file_path, thumb=thumb, caption=caption, file_name=safe_name,
                    title=title[:60] if title else "",
                    performer=artist[:60] if artist else "",
                    duration=resolved_duration,
                )
            elif kind == "video":
                media = InputMediaVideo(
                    file_path, thumb=thumb, caption=caption, file_name=safe_name,
                    duration=resolved_duration, width=width, height=height,
                    supports_streaming=True,
                )
            elif kind == "photo":
                media = InputMediaPhoto(file_path, caption=caption)
            else:
                media = InputMediaDocument(file_path, caption=caption, file_name=safe_name)

            await client.edit_inline_media(inline_message_id, media)

        finally:
            self._cleanup(file_path, thumb_path)


downloader = MediaDownloader()
