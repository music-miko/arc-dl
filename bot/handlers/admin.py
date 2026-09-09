# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo
from ..locale import text as t
from ..utils.buttons import keyboards
from ..utils.helper import (
    admin_filter,
    broadcast_to_users,
    format_stats_text,
    uptime,
)
from . import admin_registry as registry


@registry.on(MessageHandler, filters.command("stats") & admin_filter)
async def stats_cmd(client, message: Message):
    lang = await mongo.get_lang(message.from_user.id)
    total_users = await mongo.user_count()
    total_clones = await mongo.clone_count()
    running_clones = len(clones.active)
    await message.reply_text(
        format_stats_text(total_users, total_clones, running_clones, uptime.elapsed_str(), lang),
        reply_markup=keyboards.updates_channel_markup(lang),
    )


@registry.on(MessageHandler, filters.command("broadcast") & admin_filter)
async def broadcast_cmd(client, message: Message):
    lang = await mongo.get_lang(message.from_user.id)
    if not message.reply_to_message:
        await message.reply_text(t("broadcast_reply_required_text", lang))
        return

    user_ids = await mongo.all_user_ids()
    status = await message.reply_text(t("broadcast_starting_text", lang, count=len(user_ids)))

    sent, failed = await broadcast_to_users(message.reply_to_message, user_ids, status, lang)
    await status.edit_text(t("broadcast_finished_text", lang, sent=sent, failed=failed))


registry.attach(app)
