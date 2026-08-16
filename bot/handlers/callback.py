# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""Callback-query handlers for the "Download" and playlist-page buttons."""

from pyrogram import filters
from pyrogram.types import CallbackQuery

from ..core.client import app
from ..dl.actions import run_download
from ..utils.cache import cache
from ..utils.keyboards import keyboards
from ..utils.texts import STARTING_TEXT


@app.on_callback_query(filters.regex(r"^dl:"))
async def download_cb(client, callback_query: CallbackQuery):
    await callback_query.answer(STARTING_TEXT)

    token = callback_query.data.split(":", 1)[1]
    status = await callback_query.message.reply_text(STARTING_TEXT)
    await run_download(client, token, chat_id=callback_query.message.chat.id, status=status)


@app.on_callback_query(filters.regex(r"^list:"))
async def paginate_cb(client, callback_query: CallbackQuery):
    _, list_token, page_str = callback_query.data.split(":", 2)
    page = int(page_str)

    list_entry = cache.get(list_token)
    if not list_entry:
        await callback_query.answer("This list expired — please search again.", show_alert=True)
        return

    await callback_query.answer()
    await callback_query.edit_message_reply_markup(
        reply_markup=keyboards.paginated_results_keyboard(list_token, list_entry["entries"], page)
    )


@app.on_callback_query(filters.regex(r"^noop$"))
async def noop_cb(client, callback_query: CallbackQuery):
    await callback_query.answer()
