# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import CallbackQuery, Message

from ..core.client import app
from ..core.mongo import mongo
from ..locale import language_names, text as t
from ..utils.buttons import keyboards
from . import lang_registry as registry


@registry.on(MessageHandler, filters.command("lang"))
async def lang_cmd(client, message: Message):
    lang = await mongo.get_lang(message.from_user.id) if message.from_user else "en"
    await message.reply_text(t("lang_prompt_text", lang), reply_markup=keyboards.lang_keyboard())


@registry.on(CallbackQueryHandler, filters.regex(r"^setlang:"))
async def set_lang_cb(client, callback_query: CallbackQuery):
    code = callback_query.data.split(":", 1)[1]
    lang = await mongo.set_lang(callback_query.from_user.id, code)
    await callback_query.answer()
    body = t("lang_set_text", lang, language=language_names[lang])
    if callback_query.message:
        await callback_query.message.edit_text(body)
    else:
        await callback_query.answer(body, show_alert=True)


registry.attach(app)
