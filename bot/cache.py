"""
Search/playlist results are shown as buttons, but Telegram callback_data is
capped at 64 bytes — nowhere near enough for a Spotify URL or full track
metadata. So each button gets a short token, and the actual info (source
type, url/id, title, artist, duration, thumbnail) lives here in memory,
looked up when the button is pressed.

This is intentionally a simple bounded LRU-ish dict, not a database — these
entries are only useful for as long as the message with the button is on
screen, and losing them on a restart just means "please search again",
which is a fine failure mode for a downloader bot.
"""

import uuid
from collections import OrderedDict

_MAX_ENTRIES = 5000

_store: "OrderedDict[str, dict]" = OrderedDict()


def put(token: str, data: dict) -> None:
    _store[token] = data
    _store.move_to_end(token)
    while len(_store) > _MAX_ENTRIES:
        _store.popitem(last=False)


def put_new(data: dict) -> str:
    token = uuid.uuid4().hex[:10]
    put(token, data)
    return token


def get(token: str) -> dict | None:
    return _store.get(token)
