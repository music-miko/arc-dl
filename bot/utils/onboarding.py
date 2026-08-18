# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import re

from pyrogram.types import KeyboardButton, KeyboardButtonRequestManagedBot, ReplyKeyboardMarkup


def suggest_clone_username(user) -> str:
    base = re.sub(r"[^a-zA-Z0-9]", "", (user.first_name or "user")).lower()[:20] or "user"
    return f"{base}_arc_downloader_bot"[:32]


def build_clone_keyboard(user) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                "🤖 Clone this bot",
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    button_id=1,
                    suggested_name=f"{(user.first_name or 'My').strip()}'s Arc Downloader"[:64],
                    suggested_username=suggest_clone_username(user),
                ),
            )
        ]],
        resize_keyboard=True,
    )
