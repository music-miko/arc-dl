# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..core.clones import clones
from ..core.mongo import mongo
from .texts import NO_CLONES_TEXT, YOUR_CLONES_TEXT


def build_clone_list_keyboard(docs: list[dict]) -> InlineKeyboardMarkup:
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


async def render_clone_list(owner_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    docs = await mongo.clones_for_owner(owner_id)
    if not docs:
        return NO_CLONES_TEXT, None
    return YOUR_CLONES_TEXT, build_clone_list_keyboard(docs)
