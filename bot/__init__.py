# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import logging
import sys

__version__ = "1.0.0"
__bot_name__ = "ArcDLBot"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

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
    NO_RESULTS_TEXT,
    PRIVACY_TEXT,
    PROCESSING_TEXT,
    SENDING_TEXT,
    STARTING_TEXT,
    START_TEXT,
    UNSUPPORTED_LINK_TEXT,
)
from .dl import (
    YTAPIError,
    downloader,
    resolve_cdn,
    run_download,
    yt_api,
)
