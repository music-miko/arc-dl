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
from ..core.config import config
from ..utils.format import duration_to_seconds, guess_kind_from_ext, sanitize_filename, truncate
from ..utils.keyboards import keyboards
from ..utils.mime import sniffer
from .ffmpeg import ensure_audio, probe_video_meta


class MediaDownloader:
    def __init__(self):
        self.download_dir = "downloads"
        self.fetch_timeout = 300.0
        self.fetch_retries = 2
        self.ok_statuses = {200, 206}
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
        os.makedirs(self.download_dir, exist_ok=True)

    async def _download_http(self, url: str, dest_path_no_ext: str) -> tuple[str, str]:
        last_error: Exception | None = None

        for attempt in range(1, self.fetch_retries + 1):
            try:
                return await self._download_http_once(url, dest_path_no_ext)
            except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self.fetch_retries:
                    LOGGER.warning("CDN fetch failed (attempt %d/%d): %s — retrying", attempt, self.fetch_retries, e)
                    await asyncio.sleep(1.5)

        raise RuntimeError(f"CDN fetch failed after {self.fetch_retries} attempts: {last_error}")

    async def _download_http_once(self, url: str, dest_path_no_ext: str) -> tuple[str, str]:
        timeout = aiohttp.ClientTimeout(total=self.fetch_timeout)
        async with aiohttp.ClientSession(headers=self.cdn_headers) as session:
            async with session.get(url, timeout=timeout) as r:
                if r.status not in self.ok_statuses:
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

    # Ordered so the more specific media types are matched first; each maps
    # to the "kind" our pipeline understands (audio / video / photo / document).
    _TELEGRAM_MEDIA_KINDS: tuple[tuple[str, str], ...] = (
        ("audio", "audio"),
        ("voice", "audio"),
        ("video", "video"),
        ("animation", "video"),
        ("photo", "photo"),
        ("video_note", "video"),
        ("document", "document"),
        ("sticker", "document"),
    )

    def _detect_message_media(self, msg) -> tuple[object | None, str | None]:
        """A cached Telegram message may hold audio, video, a photo, an
        animation, or a plain document — not just audio/document/voice.
        Check every kind pyrogram supports so nothing gets missed."""
        if not msg:
            return None, None
        for attr, kind in self._TELEGRAM_MEDIA_KINDS:
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
        # Photo/animation/video_note objects don't carry file_name or
        # mime_type at all — fall back to a sane default for the kind.
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
        caption += f"\n\n@{keyboards.channel_username}"
        return caption

    async def _fetch_and_prepare(
        self, client: Client, cdn_url: str, title: str, platform: str,
    ) -> tuple[str, str, str, int, int, int]:
        job_id = uuid.uuid4().hex[:12]
        raw_base = os.path.join(self.download_dir, job_id)

        # An Arc API "cdn" value is either a direct HTTP(S) URL to the raw
        # file, or a t.me link pointing at a message Arc already cached on
        # Telegram. These need entirely different retrieval paths.
        known_kind: str | None = None
        if self.telegram_cdn_re.match(cdn_url):
            path, ext, known_kind = await self._download_telegram_cdn(client, cdn_url, raw_base)
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
            return final_path, audio_ext, "audio", 0, 0, 0

        # When the file came from a cached Telegram message we already know
        # its exact kind (audio/video/photo/document) from the message
        # itself — no need to guess. Only direct HTTP downloads, where the
        # extension can be unreliable, fall back to sniffing the file.
        kind = known_kind or guess_kind_from_ext(ext)
        if kind == "document":
            sniffed = sniffer.sniff_file(path)
            if sniffed:
                kind = sniffed
                ext = ".jpg" if sniffed == "photo" else ".mp4"

        safe_name = sanitize_filename(title)
        final_path = os.path.join(self.download_dir, f"{job_id}_{safe_name}{ext}")
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
            file_path, ext, kind, width, height, probed_duration = await self._fetch_and_prepare(
                client, cdn_url, title, platform
            )
            thumb = await self._download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
            caption = self._build_caption(title, artist)
            safe_name = sanitize_filename(title) + ext
            resolved_duration = duration_to_seconds(duration) or probed_duration

            if kind == "audio":
                await client.send_audio(
                    chat_id, audio=file_path, file_name=safe_name,
                    title=title[:60] if title else None,
                    performer=artist[:60] if artist else None,
                    duration=resolved_duration,
                    thumb=thumb, caption=caption,
                )
            elif kind == "video":
                await client.send_video(
                    chat_id, video=file_path, file_name=safe_name,
                    duration=resolved_duration,
                    width=width, height=height,
                    supports_streaming=True,
                    thumb=thumb, caption=caption,
                )
            elif kind == "photo":
                await client.send_photo(chat_id, photo=file_path, caption=caption)
            else:
                await client.send_document(chat_id, document=file_path, file_name=safe_name, caption=caption)

        finally:
            self._cleanup(file_path, thumb_path)

    async def _promote_to_file_id(
        self,
        client: Client,
        *,
        kind: str,
        file_path: str,
        thumb: str | None,
        title: str,
        artist: str,
        duration,
        width: int,
        height: int,
        safe_name: str,
        caption: str,
    ) -> tuple[str, str | None]:
        """Telegram forbids uploading a *new* file when editing an inline message —
        only a previously-uploaded file_id or a URL is accepted there. So we first
        send the file as a normal message (raw upload is fine for that) to a log
        channel the bot administers, then hand back the resulting file_id(s) so
        the caller can reference them when editing the inline message."""
        if not config.log_channel_id:
            raise RuntimeError(
                "Inline delivery isn't set up yet: the bot admin needs to set "
                "LOG_CHANNEL_ID (a private channel this bot is admin in) — "
                "Telegram doesn't allow sending files directly into inline results."
            )

        try:
            if kind == "audio":
                msg = await client.send_audio(
                    config.log_channel_id, audio=file_path, file_name=safe_name,
                    title=title[:60] if title else None,
                    performer=artist[:60] if artist else None,
                    duration=duration, thumb=thumb, caption=caption,
                )
                media_obj, thumbs = msg.audio, msg.audio.thumbs
            elif kind == "video":
                msg = await client.send_video(
                    config.log_channel_id, video=file_path, file_name=safe_name,
                    duration=duration, width=width, height=height,
                    supports_streaming=True, thumb=thumb, caption=caption,
                )
                media_obj, thumbs = msg.video, msg.video.thumbs
            elif kind == "photo":
                msg = await client.send_photo(config.log_channel_id, photo=file_path, caption=caption)
                media_obj, thumbs = msg.photo, None
            else:
                msg = await client.send_document(
                    config.log_channel_id, document=file_path, file_name=safe_name, caption=caption,
                )
                media_obj, thumbs = msg.document, msg.document.thumbs
        except RPCError as e:
            raise RuntimeError(f"Couldn't stage the file for inline delivery: {e}") from e

        thumb_file_id = thumbs[-1].file_id if thumbs else None
        return media_obj.file_id, thumb_file_id

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
        thumb_path = os.path.join(self.download_dir, f"{uuid.uuid4().hex[:12]}.jpg")
        file_path = None
        try:
            file_path, ext, kind, width, height, probed_duration = await self._fetch_and_prepare(
                client, cdn_url, title, platform
            )
            thumb = await self._download_thumbnail(thumbnail_url, thumb_path) if kind in ("audio", "video") else None
            caption = self._build_caption(title, artist)
            safe_name = sanitize_filename(title) + ext
            resolved_duration = duration_to_seconds(duration) or probed_duration

            # Step 1: raw-upload the file into the log channel (normal send, allowed)
            # to obtain a reusable file_id.
            media_file_id, thumb_file_id = await self._promote_to_file_id(
                client,
                kind=kind, file_path=file_path, thumb=thumb,
                title=title, artist=artist, duration=resolved_duration,
                width=width, height=height, safe_name=safe_name, caption=caption,
            )

            # Step 2: edit the inline message using the file_id — this is what
            # Telegram actually permits for inline media edits.
            if kind == "audio":
                media = InputMediaAudio(
                    media=media_file_id,
                    thumb=thumb_file_id,
                    caption=caption,
                    title=truncate(title, 60) if title else None,
                    performer=truncate(artist, 60) if artist else "",
                    duration=resolved_duration,
                    file_name=safe_name,
                )
            elif kind == "video":
                media = InputMediaVideo(
                    media=media_file_id,
                    thumb=thumb_file_id,
                    caption=caption,
                    duration=resolved_duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    file_name=safe_name,
                )
            elif kind == "photo":
                media = InputMediaPhoto(media=media_file_id, caption=caption)
            else:
                media = InputMediaDocument(media=media_file_id, caption=caption, file_name=safe_name)

            try:
                await client.edit_inline_media(inline_message_id, media=media)
            except RPCError as e:
                raise RuntimeError(f"Couldn't deliver that inline: {e}") from e

        finally:
            self._cleanup(file_path, thumb_path)


downloader = MediaDownloader()
