"""
/start and /privacy.

/start also handles the deep link inline-mode results send users on:
`https://t.me/<bot>?start=dl_<token>`. Telegram never tells a bot which
chat an inline result landed in, so there's no reliable way to attach a
working "download now" button to an inline result directly. Instead the
inline button opens a private chat with this exact parameter, which
starts the download right here — see bot/handlers/inline.py.
"""

import logging

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from ..core.client import app
from ..core.mongo import mongo
from ..dl.actions import run_download
from ..utils.keyboards import keyboards
from ..utils.texts import PRIVACY_TEXT, START_TEXT, STARTING_TEXT

logger = logging.getLogger("arcdl.handlers.start")


@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    if message.chat.type != ChatType.PRIVATE:
        await message.reply_text(
            f"Hi, I'm {client.me.first_name}. Message me privately to search and download.",
            reply_markup=keyboards.group_redirect_keyboard(client.me.username),
        )
        return

    args = message.command[1:]
    if args and args[0].startswith("dl_"):
        token = args[0][len("dl_"):]
        status = await message.reply_text(STARTING_TEXT)
        await run_download(client, token, chat_id=message.chat.id, status=status)
        return

    await message.reply_text(
        START_TEXT.format(bot_name=client.me.first_name, bot_username=client.me.username or ""),
        reply_markup=keyboards.start_keyboard(),
    )


@app.on_message(filters.command("privacy"))
async def privacy_cmd(client, message: Message):
    await message.reply_text(PRIVACY_TEXT)


@app.on_callback_query(filters.regex(r"^privacy$"))
async def privacy_cb(client, callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.reply_text(PRIVACY_TEXT)
