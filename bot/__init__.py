# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
ArcDLBot — a Telegram downloader bot built on Kurigram, powered by Arc API.

This file does two things:

1. Configures logging — the single place this happens — and exposes the
   result as `LOGGER`. Every other module in the package imports that
   one instance (`from .. import LOGGER`, or `from bot import LOGGER`
   from the top level) instead of calling `logging.getLogger(...)`
   itself; nothing else in the codebase should call
   `logging.basicConfig()`.
2. Re-exports everything core/dl/utils expose, so any of it can be
   reached with a short import from the top-level package, e.g.:

       from bot import app, config, mongo, run_download, yt_api, cache

   Handlers are deliberately NOT imported here — `bot/__main__.py`
   imports `bot.handlers` itself, after Mongo has connected, since
   importing that package is what registers every `@app.on_*` decorator.
"""

import logging
import sys

__version__ = "2.0.0"
__bot_name__ = "ArcDLBot"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# Kurigram/pyrogram and motor are both fairly chatty on INFO — keep the
# bot's own logs readable and let those speak up only when something's
# actually wrong.
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

LOGGER = logging.getLogger("arcdl")
LOGGER.info("%s v%s initializing...", __bot_name__, __version__)

from .core import app, config, mongo, setup_directories
from .utils import (
    cache,
    classifier,
    duration_to_seconds,
    guess_kind_from_ext,
    keyboards,
    sanitize_filename,
    truncate,
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
from .dl import (
    SOCIAL_DOWNLOAD_METHODS,
    YTAPIError,
    downloader,
    resolve_cdn,
    run_download,
    yt_api,
)
