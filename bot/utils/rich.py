# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""Rich Messages (Bot API 10.1) + Rich Message block buttons (Bot API 10.3).

Bot API 10.3 added `RichBlockButtons` / `InputRichBlockButtons`: a button
row that lives *inside* a rich message's own content — as opposed to a
classic `reply_markup` keyboard attached below it. That's what lets our
inline "⬇️ Download" result render as part of the message body itself,
which per the 10.1 changelog is explicitly supported for inline query
results (`InputRichMessageContent` is a valid `InputMessageContent`).

ftmgram tracks Bot API 10.1 (rich messages) as of writing; 10.2/10.3
support (block-based input, `InputRichBlockButtons`) may lag behind on
whatever version happens to be installed. Everything here is written to
degrade gracefully: if the running ftmgram version doesn't expose the
types we need yet, `build_download_rich_content` returns None and callers
fall back to the classic `InputTextMessageContent` + `InlineKeyboardMarkup`
combo, so the bot never breaks on an older library build.
"""

from .. import LOGGER

_rich_types_cache: dict | None = None


def _load_rich_types() -> dict | None:
    """Imports the rich-message types lazily and caches the result. This
    both avoids a hard dependency on 10.3-era classes for people running
    an older ftmgram build, and avoids re-attempting a known-missing
    import on every single call."""
    global _rich_types_cache
    if _rich_types_cache is not None:
        return _rich_types_cache or None

    try:
        from ftmgram.types import (
            InputRichBlockButtons,
            InputRichBlockParagraph,
            InputRichMessage,
            InputRichMessageContent,
            RichMessageButton,
        )
    except ImportError as e:
        LOGGER.debug("Rich message block buttons unavailable (ftmgram too old?): %s", e)
        _rich_types_cache = {}
        return None

    _rich_types_cache = {
        "InputRichBlockButtons": InputRichBlockButtons,
        "InputRichBlockParagraph": InputRichBlockParagraph,
        "InputRichMessage": InputRichMessage,
        "InputRichMessageContent": InputRichMessageContent,
        "RichMessageButton": RichMessageButton,
    }
    return _rich_types_cache


def build_download_rich_content(body: str, button_text: str, callback_data: str):
    """Builds an `InputRichMessageContent` whose content is a paragraph of
    `body` text followed by an `InputRichBlockButtons` block holding a
    single callback button — the Rich-Message-native replacement for a
    text message + separate inline keyboard.

    Returns None if the installed ftmgram build doesn't support this yet,
    so the caller can fall back to the classic approach.
    """
    types = _load_rich_types()
    if not types:
        return None

    try:
        button = types["RichMessageButton"](text=button_text, callback_data=callback_data)
        blocks = [
            types["InputRichBlockParagraph"](text=body),
            types["InputRichBlockButtons"](buttons=[[button]]),
        ]
        rich_message = types["InputRichMessage"](blocks=blocks)
        return types["InputRichMessageContent"](rich_message=rich_message)
    except Exception as e:
        # Constructor signatures for very new types can still shift
        # between pre-release ftmgram builds — never let this take the
        # bot down, just fall back to the classic keyboard.
        LOGGER.debug("Failed to build rich block-button content, falling back: %s", e)
        return None
