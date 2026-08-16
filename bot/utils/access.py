# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Admin-only access control for privileged commands (`/stats`,
`/broadcast`, ...). A single `filters.create` predicate, built once here
so handler modules just attach `admin_filter` instead of each defining
their own copy of the same check.
"""

from pyrogram import filters
from pyrogram.types import Message

from ..core.config import config


class AdminGuard:
    def __init__(self):
        self.filter = filters.create(self._check)

    def _check(self, _, __, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in config.sudo_users)


admin_guard = AdminGuard()
admin_filter = admin_guard.filter
