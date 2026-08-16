"""
Thin async wrapper around Arc API's HTTP routes. This bot never talks to
YouTube/Spotify/SoundCloud/social platforms directly — every fetch goes
through the deployed Arc API using API_KEY, exactly like any other API
consumer would.
"""

import asyncio
import logging
import os
import time

import aiohttp

from ..core.config import config

logger = logging.getLogger("arcdl.dl.api_client")

# Social-platform scrapes (Instagram, TikTok, Facebook, ...) routinely take
# longer than a plain cache lookup, so this sits at the high end of the
# 60-80s range rather than the old, too-tight 30s.
_REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "75"))
_REQUEST_RETRIES = 2


class YTAPIError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> dict:
    # aiohttp's URL builder (yarl) only accepts str/int/float query values —
    # it raises a hard TypeError on a raw Python bool ("Invalid variable
    # type: value should be str, int or float, got False of type bool").
    # Normalize any bools to "true"/"false" here, once, so no caller has to
    # remember to do it (e.g. isVideo=False for /youtube/v2/download).
    clean_params = {
        k: ("true" if v else "false") if isinstance(v, bool) else v
        for k, v in params.items()
    }
    clean_params["api_key"] = config.api_key
    url = f"{config.api_url}{path}"
    timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)

    last_error: Exception | None = None
    for attempt in range(1, _REQUEST_RETRIES + 1):
        try:
            async with session.get(url, params=clean_params, timeout=timeout) as r:
                try:
                    data = await r.json()
                except Exception:
                    text = await r.text()
                    raise YTAPIError(f"Non-JSON response ({r.status}): {text[:200]}", status=r.status)

                if r.status != 200:
                    detail = data.get("detail") if isinstance(data, dict) else data
                    raise YTAPIError(str(detail) or f"HTTP {r.status}", status=r.status)

                return data
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            last_error = e
            if attempt < _REQUEST_RETRIES:
                logger.warning("Request to %s timed out/failed (attempt %d/%d), retrying...", path, attempt, _REQUEST_RETRIES)
                await asyncio.sleep(1.5)
                continue
            raise YTAPIError(f"Request to {path} failed after {_REQUEST_RETRIES} attempts: {e}") from e

    raise YTAPIError(f"Request to {path} failed: {last_error}")


class YTAPIClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self.job_poll_interval = float(os.getenv("JOB_POLL_INTERVAL", "2"))
        self.job_poll_timeout = float(os.getenv("JOB_POLL_TIMEOUT", "180"))

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
        deadline = time.monotonic() + self.job_poll_timeout
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

            await asyncio.sleep(self.job_poll_interval)

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


SOCIAL_DOWNLOAD_METHODS: dict[str, str] = {
    # Maps the platform kind returned by utils.classifier.classify() to the
    # YTAPIClient method that handles it. Handlers and dl/actions.py use
    # this to dispatch to the right method via getattr(yt_api, ...) instead
    # of hand-writing an if/elif chain per platform.
    "instagram": "download_instagram",
    "facebook": "download_facebook",
    "threads": "download_threads",
    "bluesky": "download_bluesky",
    "tiktok": "download_tiktok",
    "twitter": "download_twitter",
}
