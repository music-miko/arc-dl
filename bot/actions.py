from pyrogram import Client

from . import cache
from .api_client import SOCIAL_DOWNLOAD_METHODS, yt_api, YTAPIError
from .downloader import deliver_to_chat, deliver_to_inline
from .texts import EXPIRED_TEXT

_SOCIAL_LABELS = {
    "instagram": "Instagram Media",
    "facebook": "Facebook Media",
    "threads": "Threads Media",
    "bluesky": "Bluesky Media",
    "tiktok": "TikTok Video",
    "twitter": "Twitter/X Media",
}


async def _resolve_cdn(entry: dict) -> tuple[str, dict]:
    """Returns (cdn_url, updated_entry) — updated_entry may have richer
    title/thumbnail/duration than what was cached, when the download API
    itself returns more authoritative metadata."""
    if entry.get("cdn"):
        # Already resolved before this was cached (e.g. SoundCloud, where
        # the API's /download call is synchronous and one-shot).
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

    if kind in SOCIAL_DOWNLOAD_METHODS:
        method = getattr(yt_api, SOCIAL_DOWNLOAD_METHODS[kind])
        result = await method(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"{kind.capitalize()} fetch failed")
        return result.get("cdn"), entry

    if kind == "soundcloud_direct_link":
        # Inline mode caches the raw link (resolving up front, before the
        # user even picks a result, would be wasted work for results they
        # never select) — resolved here instead, unlike the PM flow's
        # soundcloud_direct which resolves eagerly in handlers/search.py.
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


async def run_download(
    client: Client,
    token: str,
    *,
    chat_id: int | None = None,
    inline_message_id: str | None = None,
    status=None,
) -> None:
    """Resolves `token` and delivers the media either to `chat_id` (a
    normal chat) or `inline_message_id` (editing the message Telegram
    already inserted for a chosen inline result) — exactly one of the two
    should be set."""
    entry = cache.get(token)
    if not entry:
        await _update_status(client, chat_id, inline_message_id, status, EXPIRED_TEXT)
        return

    platform = entry["type"]
    if platform in ("soundcloud_direct", "soundcloud_direct_link"):
        platform = "soundcloud"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    duration = entry.get("duration")
    thumbnail = entry.get("thumbnail")

    if platform in _SOCIAL_LABELS and title == "Untitled":
        title = _SOCIAL_LABELS[platform]

    await _update_status(client, chat_id, inline_message_id, status, f"⏳ Downloading **{title}**…")

    try:
        cdn_url, entry = await _resolve_cdn(entry)
        title = entry.get("title") or title
        thumbnail = entry.get("thumbnail") or thumbnail
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await _update_status(client, chat_id, inline_message_id, status, f"📦 Sending **{title}**…")

        if inline_message_id:
            await deliver_to_inline(
                client, inline_message_id, cdn_url,
                title=title, artist=artist, duration=duration,
                thumbnail_url=thumbnail, platform=platform,
            )
        else:
            await deliver_to_chat(
                client, chat_id, cdn_url,
                title=title, artist=artist, duration=duration,
                thumbnail_url=thumbnail, platform=platform,
            )
            if status:
                await status.delete()

    except YTAPIError as e:
        await _update_status(client, chat_id, inline_message_id, status, f"❌ Failed: {e}")
    except Exception as e:
        await _update_status(client, chat_id, inline_message_id, status, f"❌ Something went wrong: {e}")


async def _update_status(client, chat_id, inline_message_id, status, text: str) -> None:
    try:
        if inline_message_id:
            await client.edit_inline_text(inline_message_id, text)
        elif status:
            await status.edit_text(text)
    except Exception:
        pass
