"""
Search/playlist results are shown as buttons, but Telegram callback_data
(and deep-link start params) are both capped well under what a Spotify
URL or full track metadata needs. So each button/link gets a short token,
and the actual info (source type, url/id, title, artist, duration,
thumbnail) lives here in memory, looked up when the button is pressed or
the deep link is opened.

This is intentionally a simple bounded LRU-ish store, not a database —
entries are only useful for as long as the message referencing them is on
screen, and losing them on a restart just means "please search again",
which is a fine failure mode for a downloader bot.
"""

import uuid
from collections import OrderedDict


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
