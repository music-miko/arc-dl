# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import CallbackQuery, ManagedBotUpdated, Message

from .. import LOGGER
from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo
from ..utils.clone_ui import render_clone_list
from ..utils.registry import HandlerRegistry
from ..utils.texts import (
    CLONE_DELETED_TEXT,
    CLONE_LAUNCHED_TEXT,
    CLONE_SETUP_FAILED_TEXT,
    CLONE_STARTED_TEXT,
    CLONE_START_FAILED_TEXT,
    CLONE_STOPPED_TEXT,
    NOT_YOUR_BOT_TEXT,
)

registry = HandlerRegistry(__name__)


@registry.on(MessageHandler, filters.command("mybot") & filters.private)
async def mybot_cmd(client, message: Message):
    text, markup = await render_clone_list(message.from_user.id)
    await message.reply_text(text, reply_markup=markup)


@registry.on(CallbackQueryHandler, filters.regex(r"^mybot_toggle:"))
async def mybot_toggle_cb(client, callback_query: CallbackQuery):
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer(NOT_YOUR_BOT_TEXT, show_alert=True)
        return

    if bot_id in clones.active:
        await clones.stop(bot_id)
        await callback_query.answer(CLONE_STOPPED_TEXT)
    else:
        try:
            await clones.spinup(
                bot_id, doc["token"], owner_id=doc["owner_id"], username=doc.get("username"), persist=False,
            )
            await callback_query.answer(CLONE_STARTED_TEXT)
        except Exception:
            LOGGER.exception("Failed to restart clone bot_id=%s", bot_id)
            await callback_query.answer(CLONE_START_FAILED_TEXT, show_alert=True)

    text, markup = await render_clone_list(callback_query.from_user.id)
    await callback_query.message.edit_text(text, reply_markup=markup)


@registry.on(CallbackQueryHandler, filters.regex(r"^mybot_delete:"))
async def mybot_delete_cb(client, callback_query: CallbackQuery):
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer(NOT_YOUR_BOT_TEXT, show_alert=True)
        return

    await clones.delete(bot_id)
    await callback_query.answer(CLONE_DELETED_TEXT)

    text, markup = await render_clone_list(callback_query.from_user.id)
    await callback_query.message.edit_text(text, reply_markup=markup)


@app.on_managed_bot()
async def managed_bot_created(client, managed_bot: ManagedBotUpdated):
    # Only the main bot ever receives this event: Telegram only grants the
    # bot_can_manage_bots flag (toggled via @BotFather) to a single manager
    # bot per managed-bot family, so this can't be attached to clone clients.
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
            await client.send_message(owner.id, CLONE_SETUP_FAILED_TEXT)
        except Exception:
            pass
        return

    LOGGER.info("Clone launched: @%s (bot_id=%s) for owner_id=%s", bot.username, bot.id, owner.id)
    try:
        await client.send_message(owner.id, CLONE_LAUNCHED_TEXT.format(username=bot.username))
    except Exception:
        pass


registry.attach(app)
