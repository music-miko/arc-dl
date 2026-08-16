# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Utils: link classification, the result-token cache, text copy, keyboard
builders, admin access control, uptime tracking, media-type sniffing,
and small formatting helpers — nothing here talks to Telegram or Arc API
directly.
"""

from .access import AdminGuard, admin_filter, admin_guard
from .cache import TokenCache, cache
from .classifier import MessageClassifier, classifier
from .format import duration_to_seconds, guess_kind_from_ext, sanitize_filename, truncate
from .keyboards import KeyboardBuilder, keyboards
from .mime import MediaSniffer, sniffer
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
from .uptime import UptimeTracker, uptime
