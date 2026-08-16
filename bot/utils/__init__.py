"""
Utils: link classification, the result-token cache, text copy, keyboard
builders, and small formatting helpers — nothing here talks to Telegram
or Arc API directly.
"""

from .cache import TokenCache, cache
from .classifier import MessageClassifier, classifier
from .format import duration_to_seconds, guess_kind_from_ext, sanitize_filename, truncate
from .keyboards import KeyboardBuilder, keyboards
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
