# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

import asyncio

from pyrogram import Client

from .. import LOGGER
from ..locale import default_lang, text as t
from ..utils.buttons import terabox_presenter
from ..utils.helper import status_reporter
from .api_client import YTAPIError, yt_api


class TeraboxFlow:
    def __init__(self):
        self.auto_delete_seconds = 10 * 60

    async def run(self, client: Client, url: str, *, chat_id: int, status=None, lang: str = default_lang) -> None:
        await status_reporter.update(status, t("terabox_fetching_text", lang))

        try:
            result = await yt_api.download_terabox(url)
        except YTAPIError as e:
            LOGGER.warning("Terabox fetch failed for %s: %s", url, e)
            await status_reporter.update(status, t("failed_text", lang, error=e))
            return

        files = result.get("files") or []
        if not files:
            await status_reporter.update(status, t("terabox_no_files_text", lang))
            return

        await status_reporter.update(status, t("terabox_sharing_text", lang, count=len(files)))

        sent_message_ids: list[int] = []
        failures = 0
        for f in files:
            name = f.get("name") or "Terabox file"
            if not f.get("dl_cdn") and not f.get("cdn"):
                failures += 1
                LOGGER.warning("Terabox file has no usable link at all (%s)", name)
                continue

            caption = terabox_presenter.build_caption(f)
            markup = terabox_presenter.build_buttons(f, lang)
            thumb = f.get("thumbnail")

            try:
                if thumb:
                    sent = await client.send_photo(chat_id, photo=thumb, caption=caption, reply_markup=markup)
                else:
                    sent = await client.send_message(chat_id, caption, reply_markup=markup)
                sent_message_ids.append(sent.id)
            except Exception as e:
                failures += 1
                LOGGER.warning("Terabox file share failed (%s): %r", name, e)

        if status:
            if sent_message_ids and not failures:
                await status.delete()
            elif sent_message_ids:
                await status_reporter.update(status, t("terabox_shared_partial_text", lang, sent=len(sent_message_ids), failed=failures))
            else:
                await status_reporter.update(status, t("terabox_share_all_failed_text", lang))

        if sent_message_ids:
            asyncio.create_task(
                self._auto_delete_messages(client, chat_id, sent_message_ids)
            )

    async def _auto_delete_messages(self, client: Client, chat_id: int, message_ids: list[int]) -> None:
        await asyncio.sleep(self.auto_delete_seconds)
        try:
            await client.delete_messages(chat_id, message_ids)
            LOGGER.info(
                "Auto-deleted %d Terabox message(s) in chat %s after %ds",
                len(message_ids), chat_id, self.auto_delete_seconds,
            )
        except Exception as e:
            LOGGER.debug("Terabox auto-delete failed for chat %s: %s", chat_id, e)


terabox_flow = TeraboxFlow()
