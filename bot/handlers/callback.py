# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery

from ..core.client import app
from ..core.mongo import mongo
from ..dl.actions import run_download
from ..locale import text as t
from ..utils.buttons import keyboards
from ..utils.helper import cache
from . import callback_registry as registry


@registry.on(CallbackQueryHandler, filters.regex(r"^dl:"))
async def download_cb(client, callback_query: CallbackQuery):
    lang = await mongo.get_lang(callback_query.from_user.id)

    if not callback_query.message:
        await callback_query.answer(t("expired_text", lang), show_alert=True)
        return

    token = callback_query.data.split(":", 1)[1]
    await callback_query.answer(t("starting_text", lang))
    status = await callback_query.message.reply_text(t("starting_text", lang))
    await run_download(client, token, chat_id=callback_query.message.chat.id, status=status, lang=lang)


@registry.on(CallbackQueryHandler, filters.regex(r"^list:"))
async def paginate_cb(client, callback_query: CallbackQuery):
    lang = await mongo.get_lang(callback_query.from_user.id)
    _, list_token, page_str = callback_query.data.split(":", 2)
    page = int(page_str)

    list_entry = cache.get(list_token)
    if not list_entry:
        await callback_query.answer(t("list_expired_text", lang), show_alert=True)
        return

    await callback_query.answer()
    await callback_query.edit_message_reply_markup(
        reply_markup=keyboards.paginated_results_keyboard(list_token, list_entry["entries"], page, lang=lang)
    )


@registry.on(CallbackQueryHandler, filters.regex(r"^noop$"))
async def noop_cb(client, callback_query: CallbackQuery):
    await callback_query.answer()


registry.attach(app)
