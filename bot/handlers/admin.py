import asyncio
import logging
import time

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from ..core.client import app
from ..core.config import config
from ..core.mongo import mongo

logger = logging.getLogger("arcdl.handlers.admin")

_START_TIME = time.time()


def _is_admin(_, __, message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in config.sudo_users)


admin_filter = filters.create(_is_admin)


def _uptime_str() -> str:
    elapsed = int(time.time() - _START_TIME)
    d, rem = divmod(elapsed, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{d}d" for _ in [1] if d] + [f"{h}h" for _ in [1] if h] + [f"{m}m" for _ in [1] if m]
    parts.append(f"{s}s")
    return "".join(parts)


@app.on_message(filters.command("stats") & admin_filter)
async def stats_cmd(client, message: Message):
    total_users = await mongo.user_count()
    text = (
        "Bot Stats\n\n"
        f"Users: {total_users}\n"
        f"Uptime: {_uptime_str()}\n"
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
            # Most common cause: user blocked the bot / deactivated account.
            failed += 1
            await mongo.remove_user(uid)

        if i % 25 == 0:
            try:
                await status.edit_text(f"Broadcasting... {i}/{total} (sent {sent}, failed {failed})")
            except Exception:
                pass
        await asyncio.sleep(0.05)  # gentle throttle to stay well under flood limits

    await status.edit_text(f"Broadcast finished.\nSent: {sent}\nFailed: {failed}")
