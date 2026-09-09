# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

import asyncio
import re
import time
import uuid
from collections import OrderedDict
from typing import Any, Callable

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from .. import LOGGER
from ..core.config import config
from ..core.mongo import mongo
from ..locale import default_lang, text as t


class MojibakeFixer:
    def __init__(self):
        self.pattern = re.compile(
            r'\\u(?P<hi>[dD][89abAB][0-9a-fA-F]{2})\\u(?P<lo>[dD][c-fC-F][0-9a-fA-F]{2})'
            r'|\\u(?P<code>[0-9a-fA-F]{4})'
            r'|\\(?P<named>[nrt"\\/])'
        )
        self.named_escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\", "/": "/"}

    def _sub(self, m) -> str:
        if m.group("hi") and m.group("lo"):
            high, low = int(m.group("hi"), 16), int(m.group("lo"), 16)
            return chr(0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00))
        if m.group("code"):
            return chr(int(m.group("code"), 16))
        return self.named_escapes[m.group("named")]

    def fix(self, text: str | None) -> str | None:
        if not text or "\\" not in text:
            return text
        return self.pattern.sub(self._sub, text)


mojibake_fixer = MojibakeFixer()


class TokenCache:
    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self.store: "OrderedDict[str, dict]" = OrderedDict()

    def put(self, token: str, data: dict) -> None:
        self.store[token] = data
        self.store.move_to_end(token)
        while len(self.store) > self.max_entries:
            self.store.popitem(last=False)

    def put_new(self, data: dict) -> str:
        token = uuid.uuid4().hex[:10]
        self.put(token, data)
        return token

    def get(self, token: str) -> dict | None:
        return self.store.get(token)


cache = TokenCache()


class HandlerRegistry:
    def __init__(self, name: str):
        self.name = name
        self._entries: list[tuple[type, Callable, Any]] = []

    def on(self, handler_cls: type, filters: Any = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._entries.append((handler_cls, func, filters))
            return func
        return decorator

    def attach(self, client: Client) -> int:
        for handler_cls, func, filt in self._entries:
            client.add_handler(handler_cls(func, filt))
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


class UptimeTracker:
    def __init__(self):
        self.start_time = time.time()

    def elapsed_str(self) -> str:
        elapsed = int(time.time() - self.start_time)
        d, rem = divmod(elapsed, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        parts = [f"{d}d" for _ in [1] if d] + [f"{h}h" for _ in [1] if h] + [f"{m}m" for _ in [1] if m]
        parts.append(f"{s}s")
        return "".join(parts)


uptime = UptimeTracker()


class StatusReporter:
    async def update(self, status: Message | None, message: str) -> None:
        if not status:
            return
        try:
            await status.edit_text(message)
        except Exception as e:
            LOGGER.debug("Could not edit status message: %s", e)


status_reporter = StatusReporter()


def format_stats_text(total_users: int, total_clones: int, running_clones: int, uptime_str: str, lang: str = default_lang) -> str:
    return t(
        "stats_text", lang,
        users=total_users, clones=total_clones, running=running_clones, uptime=uptime_str,
    )


class AdminGuard:
    def __init__(self):
        self.filter = filters.create(self._check)

    @staticmethod
    def _check(_, __, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in config.sudo_users)


admin_guard = AdminGuard()
admin_filter = admin_guard.filter


class NotCommandGuard:
    def __init__(self):
        self.filter = filters.create(self._check)

    @staticmethod
    def _check(_, __, message: Message) -> bool:
        return not (message.text or "").startswith("/")


not_command_guard = NotCommandGuard()
not_command_filter = not_command_guard.filter


async def broadcast_to_users(source: Message, user_ids: list[int], status: Message, lang: str = default_lang) -> tuple[int, int]:
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

        if i % 25 == 0:
            try:
                await status.edit_text(t("broadcast_progress_text", lang, done=i, total=total, sent=sent, failed=failed))
            except Exception:
                pass
        await asyncio.sleep(0.05)

    return sent, failed


def sanitize_filename(name: str, max_bytes: int = 150) -> str:
    name = name or "track"
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    name = re.sub(r"\s+", " ", name)
    encoded = name.encode("utf-8")
    if len(encoded) > max_bytes:
        name = encoded[:max_bytes].decode("utf-8", errors="ignore").strip()
    return name or "track"


def duration_to_seconds(duration) -> int:
    if duration is None:
        return 0
    if isinstance(duration, (int, float)):
        return int(duration)
    try:
        parts = [int(p) for p in str(duration).strip().split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def truncate(text: str, length: int) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def guess_kind_from_ext(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext in {"mp3", "m4a", "aac", "ogg", "opus", "wav", "flac"}:
        return "audio"
    if ext in {"mp4", "mov", "mkv", "webm", "m3u8", "ts"}:
        return "video"
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"
    return "document"
