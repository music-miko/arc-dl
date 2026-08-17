# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery

from ..core.client import app
from ..dl.actions import run_download
from ..utils.cache import cache
from ..utils.keyboards import keyboards
from ..utils.texts import STARTING_TEXT


async def download_cb(client, callback_query: CallbackQuery):
    # "dl:" buttons only ever come from the private/group search & playlist
    # flows (search.py, results_keyboard/paginated_results_keyboard) — inline
    # mode now answers with the CDN url directly and never attaches one of
    # these buttons, so there's no inline_message_id case to handle here.
    if not callback_query.message:
        await callback_query.answer("This result has expired. Please search again.", show_alert=True)
        return

    token = callback_query.data.split(":", 1)[1]
    await callback_query.answer(STARTING_TEXT)
    status = await callback_query.message.reply_text(STARTING_TEXT)
    await run_download(client, token, chat_id=callback_query.message.chat.id, status=status)


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


async def noop_cb(client, callback_query: CallbackQuery):
    await callback_query.answer()


HANDLERS = [
    (CallbackQueryHandler, download_cb, filters.regex(r"^dl:")),
    (CallbackQueryHandler, paginate_cb, filters.regex(r"^list:")),
    (CallbackQueryHandler, noop_cb, filters.regex(r"^noop$")),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
