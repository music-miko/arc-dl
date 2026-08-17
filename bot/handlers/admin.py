# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from ..core.client import app
from ..core.clones import clones
from ..core.mongo import mongo
from ..utils.access import admin_filter
from ..utils.uptime import uptime


@app.on_message(filters.command("stats") & admin_filter)
async def stats_cmd(client, message: Message):
    total_users = await mongo.user_count()
    total_clones = await mongo.clone_count()
    running_clones = len(clones.active)
    text = (
        "Bot Stats\n\n"
        f"Users: {total_users}\n"
        f"Clones: {total_clones} total, {running_clones} running\n"
        f"Uptime: {uptime.elapsed_str()}\n"
    )
    await message.reply_text(text)


@app.on_message(filters.command("broadcast") & admin_filter)
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Reply to the message you want to broadcast with /broadcast.")
        return

    user_ids = await mongo.all_user_ids()
    total = len(user_ids)
    status = await message.reply_text(f"Broadcasting to {total} users...")

    sent = failed = 0
    for i, uid in enumerate(user_ids, start=1):
        try:
            await message.reply_to_message.copy(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(uid)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
            await mongo.remove_user(uid)

        if i % 25 == 0:
            try:
                await status.edit_text(f"Broadcasting... {i}/{total} (sent {sent}, failed {failed})")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status.edit_text(f"Broadcast finished.\nSent: {sent}\nFailed: {failed}")
