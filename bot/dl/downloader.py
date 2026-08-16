"""
Fetches whatever cdn url Arc API handed back (a plain HTTP file, or a
Telegram-cached message) and sends it to the user — force-converting to
mp3 only for YouTube audio. `DOWNLOAD_DIR`, `FETCH_TIMEOUT`, and the
Telegram-cdn regex all live as `self.xxx` here, set up once in `__init__`,
since this is the only file that needs any of them.
"""

import asyncio
import contextlib
import logging
import os
import re
import uuid
from urllib.parse import urlparse

import aiohttp
from pyrogram import Client

from .ffmpeg import ensure_mp3
from ..utils.format import duration_to_seconds, guess_kind_from_ext, sanitize_filename
from ..utils.keyboards import keyboards

logger = logging.getLogger("arcdl.dl.downloader")

# A bare aiohttp request with no headers gets blocked or served an empty
# body by several CDNs (Instagram/Facebook's fbcdn in particular), so every
# CDN fetch goes out looking like an ordinary browser request.
_CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

# CDNs are free to answer with 206 Partial Content even when nothing asked
# for a byte range (some always chunk large media responses this way) — it
# still carries the full, usable body, so it belongs alongside 200 here.
_OK_STATUSES = {200, 206}

_FETCH_RETRIES = 2


class MediaDownloader:
    def __init__(self):
        self.download_dir = os.getenv("DOWNLOAD_DIR", "downloads")
        self.fetch_timeout = float(os.getenv("FETCH_TIMEOUT", "300"))
        self.telegram_cdn_re = re.compile(r"https?://(?:t\.me|telegram\.dog)/([^/]+)/(\d+)")
        os.makedirs(self.download_dir, exist_ok=True)

    # ---------------- fetching ----------------

    async def _download_http(self, url: str, dest_path_no_ext: str) -> tuple[str, str]:
        """Downloads url to dest_path_no_ext + detected extension. Returns
        (actual_path, ext). Retries once on a timeout/empty body, since
        flaky social-platform CDNs are the norm rather than the exception."""
        last_error: Exception | None = None

        for attempt in range(1, _FETCH_RETRIES + 1):
            try:
                return await self._download_http_once(url, dest_path_no_ext)
            except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < _FETCH_RETRIES:
                    logger.warning("CDN fetch failed (attempt %d/%d): %s — retrying", attempt, _FETCH_RETRIES, e)
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
        if not msg or not (msg.audio or msg.document or msg.voice):
            raise RuntimeError("Cached Telegram message has no downloadable media")

        dest_path = dest_path_no_ext + ".mp3"
        await client.download_media(msg, file_name=dest_path)
        return dest_path, ".mp3"

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
        """Downloads cdn_url, force-converts to mp3 ONLY when platform is
        'youtube' (every other platform is sent exactly as fetched — no
        transcoding). Returns (file_path, ext, kind) where kind is one of
        audio/video/photo/document."""
        job_id = uuid.uuid4().hex[:12]
        raw_base = os.path.join(self.download_dir, job_id)

        if self.telegram_cdn_re.match(cdn_url):
            path, ext = await self._download_telegram_cdn(client, cdn_url, raw_base)
        else:
            path, ext = await self._download_http(cdn_url, raw_base)

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise RuntimeError("Downloaded file is empty")

        if platform == "youtube":
            mp3_path = await ensure_mp3(path)
            if mp3_path != path:
                with contextlib.suppress(Exception):
                    os.remove(path)
            safe_name = sanitize_filename(title)
            final_path = os.path.join(self.download_dir, f"{job_id}_{safe_name}.mp3")
            os.replace(mp3_path, final_path)
            return final_path, ".mp3", "audio"

        kind = guess_kind_from_ext(ext)
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

    # ---------------- delivery ----------------

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
        """Fetches cdn_url and sends it to chat_id, named after the title.
        Raises on failure — callers show the error to the user."""
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


downloader = MediaDownloader()
