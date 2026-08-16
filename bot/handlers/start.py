from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from bot.client import app
from bot.database import touch_user
from bot.keyboards import group_redirect_keyboard, start_keyboard
from bot.texts import PRIVACY_TEXT, START_TEXT


@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    user = message.from_user
    if user:
        await touch_user(user.id, user.first_name or "", user.username)

    me = await client.get_me()

    if message.chat.type != ChatType.PRIVATE:
        await message.reply_text(
            f"👋 Hey, I'm **{me.first_name}**! Message me privately to search & download.",
            reply_markup=group_redirect_keyboard(me.username),
        )
        return

    await message.reply_text(
        START_TEXT.format(bot_name=me.first_name, bot_username=me.username or ""),
        reply_markup=start_keyboard(),
    )


@app.on_message(filters.command("privacy"))
async def privacy_cmd(client, message: Message):
    await message.reply_text(PRIVACY_TEXT)


@app.on_callback_query(filters.regex(r"^privacy$"))
async def privacy_cb(client, callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.reply_text(PRIVACY_TEXT)
