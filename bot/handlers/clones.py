# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ManagedBotUpdated, Message

from .. import LOGGER
from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo


def _mybot_keyboard(docs: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for doc in docs:
        bot_id = doc["_id"]
        username = doc.get("username") or str(bot_id)
        running = bot_id in clones.active
        rows.append([InlineKeyboardButton(f"@{username} — {'Running' if running else 'Stopped'}", callback_data="noop")])
        rows.append([
            InlineKeyboardButton("⏹ Stop" if running else "▶️ Start", callback_data=f"mybot_toggle:{bot_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"mybot_delete:{bot_id}"),
        ])
    return InlineKeyboardMarkup(rows)


async def _render_mybot(owner_id: int):
    docs = await mongo.clones_for_owner(owner_id)
    if not docs:
        return "You haven't cloned this bot yet. Tap Clone this bot in /start to create one.", None
    return "Your cloned bots:", _mybot_keyboard(docs)


async def mybot_cmd(client, message: Message):
    text, markup = await _render_mybot(message.from_user.id)
    await message.reply_text(text, reply_markup=markup)


async def mybot_toggle_cb(client, callback_query: CallbackQuery):
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer("This isn't your bot.", show_alert=True)
        return

    if bot_id in clones.active:
        await clones.stop(bot_id)
        await callback_query.answer("Bot stopped.")
    else:
        try:
            await clones.spinup(
                bot_id, doc["token"], owner_id=doc["owner_id"], username=doc.get("username"), persist=False,
            )
            await callback_query.answer("Bot started.")
        except Exception:
            LOGGER.exception("Failed to restart clone bot_id=%s", bot_id)
            await callback_query.answer("Couldn't start that bot — its token may have been revoked.", show_alert=True)

    text, markup = await _render_mybot(callback_query.from_user.id)
    await callback_query.message.edit_text(text, reply_markup=markup)


async def mybot_delete_cb(client, callback_query: CallbackQuery):
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer("This isn't your bot.", show_alert=True)
        return

    await clones.delete(bot_id)
    await callback_query.answer("Bot deleted.")

    text, markup = await _render_mybot(callback_query.from_user.id)
    await callback_query.message.edit_text(text, reply_markup=markup)


@app.on_managed_bot()
async def managed_bot_created(client, managed_bot: ManagedBotUpdated):
    owner, bot = managed_bot.user, managed_bot.bot

    try:
        token = await client.get_managed_bot_token(bot.id)
    except Exception:
        LOGGER.exception("Failed to export token for managed bot_id=%s", bot.id)
        return

    try:
        clone_client = await clones.spinup(bot.id, token, owner_id=owner.id, username=bot.username)
        await clones.set_branding(clone_client)
    except Exception:
        LOGGER.exception("Failed to launch clone bot_id=%s", bot.id)
        try:
            await client.send_message(
                owner.id, "Something went wrong setting up your cloned bot. Please try again with /start."
            )
        except Exception:
            pass
        return

    LOGGER.info("Clone launched: @%s (bot_id=%s) for owner_id=%s", bot.username, bot.id, owner.id)
    try:
        await client.send_message(
            owner.id,
            f"Your bot @{bot.username} is live and works exactly like this one.\n\n"
            "Everything's ready — search, links, and inline mode all work.\n\n"
            "Manage it anytime with /mybot.",
        )
    except Exception:
        pass


app.add_handler(MessageHandler(mybot_cmd, filters.command("mybot") & filters.private))
app.add_handler(CallbackQueryHandler(mybot_toggle_cb, filters.regex(r"^mybot_toggle:")))
app.add_handler(CallbackQueryHandler(mybot_delete_cb, filters.regex(r"^mybot_delete:")))
