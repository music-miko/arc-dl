"""
Inline keyboard builders. `PLAYLIST_PAGE_SIZE` lives here as `self.
playlist_page_size`, read directly from its own env var — this is the
only file that needs it, so there's no reason to route it through a
shared config object.
"""

import os

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .format import truncate

CHANNEL_URL = "https://telegram.dog/ArcUpdates"


class KeyboardBuilder:
    def __init__(self):
        self.playlist_page_size = int(os.getenv("PLAYLIST_PAGE_SIZE", "8"))

    def results_keyboard(self, entries: list[tuple[str, dict]]) -> InlineKeyboardMarkup:
        """entries: list of (token, meta) where meta has 'title' and 'duration'.
        Used for buttons the bot sends itself in a private chat."""
        rows = []
        for token, meta in entries:
            label = truncate(meta.get("title") or "Untitled", 45)
            duration = meta.get("duration")
            if duration:
                label = f"{label} - {duration}"
            rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}")])
        return InlineKeyboardMarkup(rows)

    def paginated_results_keyboard(
        self, list_token: str, entries: list[tuple[str, dict]], page: int
    ) -> InlineKeyboardMarkup:
        """entries: the FULL track list as (token, meta) pairs — slicing to
        the current page happens here. Each track gets its own download
        button; Prev/Next only changes which page is shown, it never
        downloads anything by itself (so a playlist is never fetched all at
        once)."""
        page_size = self.playlist_page_size
        total_pages = max(1, (len(entries) + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))

        start = page * page_size
        page_entries = entries[start:start + page_size]

        rows = []
        for token, meta in page_entries:
            label = truncate(meta.get("title") or "Untitled", 40)
            duration = meta.get("duration")
            if duration:
                label = f"{label} - {duration}"
            rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("< Prev", callback_data=f"list:{list_token}:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next >", callback_data=f"list:{list_token}:{page + 1}"))
        if len(nav) > 1:
            rows.append(nav)

        return InlineKeyboardMarkup(rows)

    def group_redirect_keyboard(self, bot_username: str) -> InlineKeyboardMarkup | None:
        if not bot_username:
            return None
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open in private", url=f"https://t.me/{bot_username}")]]
        )

    def start_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("Privacy", callback_data="privacy")],
        ])

    def inline_download_keyboard(self, bot_username: str, token: str) -> InlineKeyboardMarkup:
        """Inline-mode results can't attach a working "download now" button
        directly — Telegram never tells the bot which chat an inline result
        landed in, so the bot has no reliable way to deliver a file to it.
        Instead this deep-links back into a private chat with the bot,
        which starts the download there (see bot/handlers/start.py)."""
        url = f"https://t.me/{bot_username}?start=dl_{token}"
        return InlineKeyboardMarkup([[InlineKeyboardButton("Download", url=url)]])


keyboards = KeyboardBuilder()
