# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..core.config import config
from ..core.mongo import mongo
from ..utils.keyboards import keyboards
from ..utils.onboarding import build_clone_keyboard
from ..utils.registry import HandlerRegistry
from ..utils.texts import CLONE_HINT_TEXT, PRIVACY_TEXT, START_TEXT

registry = HandlerRegistry(__name__)


@registry.on(MessageHandler, filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    is_main = client.me.id == config.bot_id
    text = START_TEXT.format(bot_name=client.me.first_name, bot_username=client.me.username or "")

    if is_main:
        await message.reply_text(
            text + CLONE_HINT_TEXT,
            reply_markup=build_clone_keyboard(user) if user else None,
        )
    else:
        await message.reply_text(text, reply_markup=keyboards.start_keyboard(client.me.username or ""))


@registry.on(MessageHandler, filters.command("privacy") & filters.private)
async def privacy_cmd(client, message: Message):
    await message.reply_text(PRIVACY_TEXT)


registry.attach(app)
