# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .format import truncate


class KeyboardBuilder:
    def __init__(self):
        self.playlist_page_size = 8
        self.channel_username = "ArcUpdates"
        self.channel_url = f"https://telegram.dog/{self.channel_username}"

    def results_keyboard(self, entries: list[tuple[str, dict]]) -> InlineKeyboardMarkup:
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

    def start_keyboard(self, bot_username: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        ])


keyboards = KeyboardBuilder()
