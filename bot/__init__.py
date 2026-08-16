"""
Arc-DL — a Telegram downloader bot built on Kurigram, powered by Arc API.

This file is the single place logging is configured. Every other module in
the package just does `logging.getLogger(__name__)` and inherits this setup
— nothing else in the codebase should call `logging.basicConfig()`.
"""

import logging
import sys

__version__ = "2.0.0"
__bot_name__ = "Arc-DL"

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

logger = logging.getLogger("arcdl")
logger.info("Arc-DL v%s initializing...", __version__)
