# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import CallbackQuery, ManagedBotUpdated, Message

from .. import LOGGER
from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo
from ..locale import text as t
from ..utils.buttons import render_clone_list
from . import clones_registry as registry


@registry.on(MessageHandler, filters.command("mybot") & filters.private)
async def mybot_cmd(client, message: Message):
    lang = await mongo.get_lang(message.from_user.id)
    text_body, markup = await render_clone_list(message.from_user.id, lang)
    await message.reply_text(text_body, reply_markup=markup)


@registry.on(CallbackQueryHandler, filters.regex(r"^mybot_toggle:"))
async def mybot_toggle_cb(client, callback_query: CallbackQuery):
    lang = await mongo.get_lang(callback_query.from_user.id)
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer(t("not_your_bot_text", lang), show_alert=True)
        return

    if bot_id in clones.active:
        await clones.stop(bot_id)
        await callback_query.answer(t("clone_stopped_text", lang))
    else:
        try:
            await clones.spinup(
                bot_id, doc["token"], owner_id=doc["owner_id"], username=doc.get("username"), persist=False,
            )
            await callback_query.answer(t("clone_started_text", lang))
        except Exception:
            LOGGER.exception("Failed to restart clone bot_id=%s", bot_id)
            await callback_query.answer(t("clone_start_failed_text", lang), show_alert=True)

    text_body, markup = await render_clone_list(callback_query.from_user.id, lang)
    await callback_query.message.edit_text(text_body, reply_markup=markup)


@registry.on(CallbackQueryHandler, filters.regex(r"^mybot_delete:"))
async def mybot_delete_cb(client, callback_query: CallbackQuery):
    lang = await mongo.get_lang(callback_query.from_user.id)
    bot_id = int(callback_query.data.split(":", 1)[1])
    doc = await mongo.get_clone(bot_id)
    if not doc or doc["owner_id"] != callback_query.from_user.id:
        await callback_query.answer(t("not_your_bot_text", lang), show_alert=True)
        return

    await clones.delete(bot_id)
    await callback_query.answer(t("clone_deleted_text", lang))

    text_body, markup = await render_clone_list(callback_query.from_user.id, lang)
    await callback_query.message.edit_text(text_body, reply_markup=markup)


@app.on_managed_bot()
async def managed_bot_created(client, managed_bot: ManagedBotUpdated):
    owner, bot = managed_bot.user, managed_bot.bot
    lang = await mongo.get_lang(owner.id)

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
            await client.send_message(owner.id, t("clone_setup_failed_text", lang))
        except Exception:
            pass
        return

    LOGGER.info("Clone launched: @%s (bot_id=%s) for owner_id=%s", bot.username, bot.id, owner.id)
    try:
        await client.send_message(owner.id, t("clone_launched_text", lang, username=bot.username))
    except Exception:
        pass


registry.attach(app)
