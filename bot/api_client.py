"""
Thin async wrapper around the YT-API's HTTP routes. This bot never talks to
YouTube/Spotify/SoundCloud directly — every fetch goes through the deployed
YT-API using YT_API_KEY, exactly like any other API consumer would.
"""

import asyncio
import time

import aiohttp

from .config import config


class YTAPIError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> dict:
    params = {**params, "api_key": config.YT_API_KEY}
    url = f"{config.YT_API_BASE_URL}{path}"

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
        try:
            data = await r.json()
        except Exception:
            text = await r.text()
            raise YTAPIError(f"Non-JSON response ({r.status}): {text[:200]}", status=r.status)

        if r.status != 200:
            detail = data.get("detail") if isinstance(data, dict) else data
            raise YTAPIError(str(detail) or f"HTTP {r.status}", status=r.status)

        return data


class YTAPIClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ---------------- YouTube ----------------

    async def search_youtube(self, query: str, limit: int = 5) -> list[dict]:
        session = await self._get_session()
        data = await _get(session, "/youtube/v2/search", {"query": query, "limit": limit})
        return data.get("results", [])

    async def get_youtube_playlist(self, link: str, limit: int = 100) -> dict:
        session = await self._get_session()
        return await _get(session, "/youtube/v2/playlist", {"link": link, "limit": limit})

    async def download_youtube(self, query: str, is_video: bool = False) -> dict:
        """Returns the final result dict (with a 'cdn' url) — polls the job
        queue internally if the API queues a scrape instead of cache-hitting."""
        session = await self._get_session()
        data = await _get(
            session, "/youtube/v2/download", {"query": query, "isVideo": is_video}
        )

        if data.get("job_id") is None:
            result = data.get("result")
            if not result or not result.get("success"):
                raise YTAPIError("Download failed: empty result from cache lookup")
            return result

        return await self._poll_job(session, data["job_id"])

    async def _poll_job(self, session: aiohttp.ClientSession, job_id: str) -> dict:
        deadline = time.monotonic() + config.JOB_POLL_TIMEOUT
        while time.monotonic() < deadline:
            data = await _get(session, "/youtube/jobStatus", {"job_id": job_id})
            job = data.get("job", {})
            status = job.get("status")

            if status == "done":
                result = job.get("result")
                if not result or not result.get("success"):
                    raise YTAPIError(f"Download failed: {result}")
                return result
            if status == "error":
                raise YTAPIError(job.get("error") or "Download job failed")

            await asyncio.sleep(config.JOB_POLL_INTERVAL)

        raise YTAPIError("Timed out waiting for download to finish")

    # ---------------- Spotify ----------------

    async def download_spotify(self, link: str) -> dict:
        session = await self._get_session()
        data = await _get(session, "/spotify/download", {"link": link})
        if not data.get("success"):
            raise YTAPIError(data.get("error") or "Spotify download failed")
        return data

    async def get_spotify_playlist(self, link: str) -> dict:
        session = await self._get_session()
        return await _get(session, "/spotify/playlist", {"link": link})

    # ---------------- SoundCloud ----------------

    async def download_soundcloud(self, query: str) -> dict:
        session = await self._get_session()
        data = await _get(session, "/soundcloud/download", {"query": query})
        return data.get("result", {})

    # ---------------- Social platforms (no caching, no conversion) ----------------
    # All six share the same response shape: {"success", "cdn", "platform", "url"}.

    async def _download_social(self, path: str, url: str) -> dict:
        session = await self._get_session()
        return await _get(session, path, {"url": url})

    async def download_instagram(self, url: str) -> dict:
        return await self._download_social("/instagram/download", url)

    async def download_facebook(self, url: str) -> dict:
        return await self._download_social("/facebook/download", url)

    async def download_threads(self, url: str) -> dict:
        return await self._download_social("/threads/download", url)

    async def download_bluesky(self, url: str) -> dict:
        return await self._download_social("/bluesky/download", url)

    async def download_tiktok(self, url: str) -> dict:
        return await self._download_social("/tiktok/download", url)

    async def download_twitter(self, url: str) -> dict:
        return await self._download_social("/twitter/download", url)


yt_api = YTAPIClient()

# platform kind (from utils.classify_message) -> YTAPIClient method name
SOCIAL_DOWNLOAD_METHODS = {
    "instagram": "download_instagram",
    "facebook": "download_facebook",
    "threads": "download_threads",
    "bluesky": "download_bluesky",
    "tiktok": "download_tiktok",
    "twitter": "download_twitter",
}
