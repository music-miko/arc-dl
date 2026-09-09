# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..core.config import config
from ..core.mongo import mongo
from ..locale import text as t
from ..utils.buttons import build_clone_keyboard, keyboards
from . import start_registry as registry


@registry.on(MessageHandler, filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user = message.from_user
    lang = "en"
    if user:
        lang = await mongo.touch_user(user.id, user.first_name or "", user.username)

    is_main = client.me.id == config.bot_id
    body = t("start_text", lang, bot_name=client.me.first_name, bot_username=client.me.username or "")

    if is_main:
        await message.reply_text(
            body + t("clone_hint_text", lang),
            reply_markup=build_clone_keyboard(user, lang) if user else None,
        )
    else:
        await message.reply_text(body, reply_markup=keyboards.start_keyboard(client.me.username or "", lang))


@registry.on(MessageHandler, filters.command("privacy") & filters.private)
async def privacy_cmd(client, message: Message):
    lang = await mongo.get_lang(message.from_user.id) if message.from_user else "en"
    await message.reply_text(t("privacy_text", lang), reply_markup=keyboards.updates_channel_markup(lang))


registry.attach(app)
