# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo
from ..utils.access import admin_filter
from ..utils.broadcast import broadcast_to_users
from ..utils.registry import HandlerRegistry
from ..utils.stats import format_stats_text
from ..utils.uptime import uptime

registry = HandlerRegistry(__name__)


@registry.on(MessageHandler, filters.command("stats") & admin_filter)
async def stats_cmd(client, message: Message):
    total_users = await mongo.user_count()
    total_clones = await mongo.clone_count()
    running_clones = len(clones.active)
    await message.reply_text(format_stats_text(total_users, total_clones, running_clones, uptime.elapsed_str()))


@registry.on(MessageHandler, filters.command("broadcast") & admin_filter)
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Reply to the message you want to broadcast with /broadcast.")
        return

    user_ids = await mongo.all_user_ids()
    status = await message.reply_text(f"Broadcasting to {len(user_ids)} users...")

    sent, failed = await broadcast_to_users(message.reply_to_message, user_ids, status)
    await status.edit_text(f"Broadcast finished.\nSent: {sent}\nFailed: {failed}")


registry.attach(app)
