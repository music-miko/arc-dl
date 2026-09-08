# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""Terabox is handled separately from the rest of dl/actions.py: a single
share link can resolve to several files, each carrying multiple stream
qualities (see YT-API's /terabox/download), rather than the one-cdn shape
every other platform returns. Terabox downloads are also restricted to DM
only (enforced in handlers/search.py + handlers/inline.py, since that's
where a request can originate from), and delivered messages are
auto-deleted 10 minutes after being sent.
"""

import asyncio

from pyrogram import Client

from .. import LOGGER
from .api_client import YTAPIError, yt_api
from .downloader import downloader

TERABOX_AUTO_DELETE_SECONDS = 10 * 60


def _best_terabox_quality(cdn_map: dict | None) -> str | None:
    """cdn is a dict of every HLS-stream quality xAPIverse returned for
    this file, e.g. {"360p": "...m3u8", "480p": "...m3u8"}. These are
    *stream manifests* for a video player, not a single downloadable
    file — fetching one with a plain HTTP GET only returns a small text
    playlist, not the actual video, which is why files used to arrive as
    unplayable ".bin" blobs. This is now only used as an absolute
    last-resort fallback when a file has no direct download link at all."""
    if not cdn_map:
        return None
    return cdn_map.get("360p") or cdn_map.get("480p") or next(iter(cdn_map.values()), None)


async def run_terabox_download(client: Client, url: str, *, chat_id: int, status=None) -> None:
    await _update_status(status, "Fetching Terabox link...")

    try:
        result = await yt_api.download_terabox(url)
    except YTAPIError as e:
        LOGGER.warning("Terabox fetch failed for %s: %s", url, e)
        await _update_status(status, f"Failed: {e}")
        return

    files = result.get("files") or []
    if not files:
        await _update_status(status, "No files found in this Terabox link.")
        return

    await _update_status(status, f"Sending {len(files)} file(s) from Terabox...")

    sent_message_ids: list[int] = []
    failures = 0
    for f in files:
        name = f.get("name") or "Terabox file"

        # dl_cdn (the API's normal_dlink) is the real single-file direct
        # download link — always prefer it. Only fall back to a stream
        # manifest URL when there's truly nothing else, since that won't
        # produce a valid playable file (see _best_terabox_quality).
        cdn_url = f.get("dl_cdn") or _best_terabox_quality(f.get("cdn"))
        if not cdn_url:
            failures += 1
            LOGGER.warning("Terabox file has no usable link at all (%s)", name)
            continue

        try:
            sent = await downloader.deliver_to_chat(
                client, chat_id, cdn_url,
                title=name,
                duration=f.get("duration"),
                thumbnail_url=f.get("thumbnail"),
                platform="terabox",
                filename_hint=name,
            )
            if sent:
                sent_message_ids.append(sent.id)
        except Exception as e:
            failures += 1
            LOGGER.warning("Terabox file delivery failed (%s): %s", name, e)

    if status:
        if sent_message_ids and not failures:
            await status.delete()
        elif sent_message_ids:
            await _update_status(status, f"Sent {len(sent_message_ids)} file(s); {failures} failed.")
        else:
            await _update_status(status, "Couldn't deliver any files from this Terabox link.")

    if sent_message_ids:
        asyncio.create_task(
            _auto_delete_messages(client, chat_id, sent_message_ids, TERABOX_AUTO_DELETE_SECONDS)
        )


async def _auto_delete_messages(client: Client, chat_id: int, message_ids: list[int], delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_ids)
        LOGGER.info("Auto-deleted %d Terabox message(s) in chat %s after %ds", len(message_ids), chat_id, delay)
    except Exception as e:
        LOGGER.debug("Terabox auto-delete failed for chat %s: %s", chat_id, e)


async def _update_status(status, text: str) -> None:
    if not status:
        return
    try:
        await status.edit_text(text)
    except Exception as e:
        LOGGER.debug("Could not edit status message: %s", e)
