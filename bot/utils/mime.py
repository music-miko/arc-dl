# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import aiohttp


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
