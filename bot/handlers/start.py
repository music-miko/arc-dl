# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""/start and /privacy."""

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from ..core.client import app
from ..core.mongo import mongo
from ..utils.keyboards import keyboards
from ..utils.texts import PRIVACY_TEXT, START_TEXT


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
