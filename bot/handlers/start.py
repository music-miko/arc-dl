# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import re

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import KeyboardButton, KeyboardButtonRequestManagedBot, Message, ReplyKeyboardMarkup

from ..core.client import app
from ..core.config import config
from ..core.mongo import mongo
from ..utils.keyboards import keyboards
from ..utils.texts import CLONE_HINT_TEXT, PRIVACY_TEXT, START_TEXT


def _suggest_username(user) -> str:
    base = re.sub(r"[^a-zA-Z0-9]", "", (user.first_name or "user")).lower()[:20] or "user"
    return f"{base}_arc_downloader_bot"[:32]


def _clone_keyboard(user) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                "🤖 Clone this bot",
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    button_id=1,
                    suggested_name=f"{(user.first_name or 'My').strip()}'s Arc Downloader"[:64],
                    suggested_username=_suggest_username(user),
                ),
            )
        ]],
        resize_keyboard=True,
    )


async def start_cmd(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    is_main = client.me.id == config.bot_id
    text = START_TEXT.format(bot_name=client.me.first_name, bot_username=client.me.username or "")

    if is_main:
        await message.reply_text(
            text + CLONE_HINT_TEXT,
            reply_markup=_clone_keyboard(user) if user else None,
        )
    else:
        await message.reply_text(text, reply_markup=keyboards.start_keyboard(client.me.username or ""))


async def privacy_cmd(client, message: Message):
    await message.reply_text(PRIVACY_TEXT)


HANDLERS = [
    (MessageHandler, start_cmd, filters.command("start") & filters.private),
    (MessageHandler, privacy_cmd, filters.command("privacy") & filters.private),
]

for _cls, _func, _filt in HANDLERS:
    app.add_handler(_cls(_func, _filt))
