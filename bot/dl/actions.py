# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import Client

from .. import LOGGER
from ..locale import default_lang, text as t
from ..utils.classifier import classifier
from ..utils.helper import cache, mojibake_fixer, status_reporter
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
            caption_text = mojibake_fixer.fix(result.get("caption") or result.get("text"))
            author = result.get("author") or {}
            author_name = mojibake_fixer.fix(author.get("username") or author.get("name"))

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


async def run_download(client: Client, token: str, *, chat_id: int, status=None, lang: str = default_lang) -> None:
    entry = cache.get(token)
    if not entry:
        await status_reporter.update(status, t("expired_text", lang))
        return

    platform, title, artist = _resolve_title_artist(entry)
    duration = entry.get("duration")
    thumbnail = entry.get("thumbnail")

    await status_reporter.update(status, f"{t('downloading_text', lang)} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry)
        title = entry.get("title") or title
        thumbnail = entry.get("thumbnail") or thumbnail
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await status_reporter.update(status, f"{t('sending_text', lang)} {title}")

        media_group = entry.get("media_group")
        if media_group:
            await downloader.deliver_media_group_to_chat(
                client, chat_id, media_group, caption=title, platform=platform,
            )
        else:
            await downloader.deliver_to_chat(
                client, chat_id, cdn_url,
                title=title, artist=artist, duration=duration,
                thumbnail_url=thumbnail, platform=platform, lang=lang,
            )
        if status:
            await status.delete()

    except YTAPIError as e:
        LOGGER.warning("Download failed for token=%s: %s", token, e)
        await status_reporter.update(status, t("failed_text", lang, error=e))
    except Exception as e:
        LOGGER.exception("Unexpected error delivering token=%s", token)
        await status_reporter.update(status, t("something_wrong_text", lang, error=e))

