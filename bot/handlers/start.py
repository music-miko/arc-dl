# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.types import Message

from ..core.client import app
from ..core.mongo import mongo
from ..utils.keyboards import keyboards
from ..utils.texts import PRIVACY_TEXT, START_TEXT


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    await message.reply_text(
        START_TEXT.format(bot_name=client.me.first_name, bot_username=client.me.username or ""),
        reply_markup=keyboards.start_keyboard(client.me.username or ""),
    )


@app.on_message(filters.command("privacy") & filters.private)
async def privacy_cmd(client, message: Message):
    await message.reply_text(PRIVACY_TEXT)
