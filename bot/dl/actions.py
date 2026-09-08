# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import Client

from .. import LOGGER
from ..utils.classifier import classifier
from ..utils.common import cache
from ..utils.texts import DOWNLOADING_TEXT, EXPIRED_TEXT, SENDING_TEXT
from .api_client import YTAPIError, yt_api
from .downloader import downloader


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
            reason = result.get("error") or result.get("message") or f"{kind.capitalize()} fetch failed"
            raise YTAPIError(f"Unable to fetch media from {kind.capitalize()}: {reason}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url") or entry.get("thumbnail"),
        }

        if kind in ("instagram", "twitter"):
            # These two now come back from the API with much richer
            # metadata (caption/text, author, per-post stats, and — for a
            # carousel post or a multi-media tweet — the *full* media
            # list) instead of just a single cdn link. Fold the useful
            # bits into the caption and, when there's more than one media
            # item, hand the whole list off so it gets delivered as an
            # album instead of just the first item.
            caption_text = result.get("caption") or result.get("text")
            author = result.get("author") or {}
            author_name = author.get("username") or author.get("name")

            title_bits = [caption_text.strip()] if caption_text else []
            if author_name:
                title_bits.append(f"— @{author_name}" if not author_name.startswith("@") else f"— {author_name}")
            entry["title"] = " ".join(title_bits) or entry.get("title")

            media_list = result.get("media") or []
            if len(media_list) > 1:
                entry["media_group"] = media_list

        return result.get("cdn"), entry

    if kind == "applemusic":
        result = await yt_api.download_applemusic(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"Unable to fetch from Apple Music: {result.get('error', 'download failed')}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result.get("cdn"), entry

    if kind == "jiosaavn":
        result = await yt_api.download_jiosaavn(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"Unable to fetch from JioSaavn: {result.get('error', 'download failed')}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
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


def _resolve_title_artist(entry: dict) -> tuple[str, str, str]:
    platform = entry["type"]
    if platform in ("soundcloud_direct", "soundcloud_direct_link"):
        platform = "soundcloud"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    if platform in classifier.social_labels and title == "Untitled":
        title = classifier.social_labels[platform]
    return platform, title, artist


async def run_download(client: Client, token: str, *, chat_id: int, status=None) -> None:
    entry = cache.get(token)
    if not entry:
        await _update_status(status, EXPIRED_TEXT)
        return

    platform, title, artist = _resolve_title_artist(entry)
    duration = entry.get("duration")
    thumbnail = entry.get("thumbnail")

    await _update_status(status, f"{DOWNLOADING_TEXT} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        thumbnail = entry.get("thumbnail") or thumbnail
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await _update_status(status, f"{SENDING_TEXT} {title}")

        media_group = entry.get("media_group")
        if media_group:
            await downloader.deliver_media_group_to_chat(
                client, chat_id, media_group, caption=title, platform=platform,
            )
        else:
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


async def _update_status(status, text: str) -> None:
    if not status:
        return
    try:
        await status.edit_text(text)
    except Exception as e:
        LOGGER.debug("Could not edit status message: %s", e)
