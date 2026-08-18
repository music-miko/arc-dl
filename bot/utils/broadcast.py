# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio

from pyrogram.errors import FloodWait
from pyrogram.types import Message

from ..core.mongo import mongo

PROGRESS_INTERVAL = 25
THROTTLE_SECONDS = 0.05


async def broadcast_to_users(source: Message, user_ids: list[int], status: Message) -> tuple[int, int]:
    total = len(user_ids)
    sent = failed = 0

    for i, uid in enumerate(user_ids, start=1):
        try:
            await source.copy(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await source.copy(uid)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
            await mongo.remove_user(uid)

        if i % PROGRESS_INTERVAL == 0:
            try:
                await status.edit_text(f"Broadcasting... {i}/{total} (sent {sent}, failed {failed})")
            except Exception:
                pass
        await asyncio.sleep(THROTTLE_SECONDS)

    return sent, failed
