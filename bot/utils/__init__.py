"""
Utils: link classification, the result-token cache, text copy, keyboard
builders, and small formatting helpers — nothing here talks to Telegram
or Arc API directly.
"""

from .cache import TokenCache, cache
from .classifier import MessageClassifier, classifier
from .format import duration_to_seconds, guess_kind_from_ext, sanitize_filename, truncate
from .keyboards import CHANNEL_URL, KeyboardBuilder, keyboards
from .texts import (
    DOWNLOADING_TEXT,
    EXPIRED_TEXT,
    GROUP_REDIRECT_TEXT,
    NO_RESULTS_TEXT,
    PRIVACY_TEXT,
    PROCESSING_TEXT,
    SENDING_TEXT,
    STARTING_TEXT,
    START_TEXT,
    UNSUPPORTED_LINK_TEXT,
)

__all__ = [
    "cache", "TokenCache",
    "classifier", "MessageClassifier",
    "sanitize_filename", "duration_to_seconds", "truncate", "guess_kind_from_ext",
    "keyboards", "KeyboardBuilder", "CHANNEL_URL",
    "START_TEXT", "PRIVACY_TEXT", "GROUP_REDIRECT_TEXT", "EXPIRED_TEXT",
    "PROCESSING_TEXT", "DOWNLOADING_TEXT", "SENDING_TEXT", "STARTING_TEXT",
    "NO_RESULTS_TEXT", "UNSUPPORTED_LINK_TEXT",
]
