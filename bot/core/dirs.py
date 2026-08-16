# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Filesystem setup for the bot's own working directories. Right now that's
just the scratch folder downloaded files live in for the few seconds
between being fetched and being sent — `bot/dl/downloader.py` reads the
same `DOWNLOAD_DIR` env var directly for its own use, this module's only
job is making sure the folder actually exists before the bot starts
accepting messages.
"""

import os

from .. import LOGGER


def setup_directories() -> None:
    download_dir = os.getenv("DOWNLOAD_DIR", "downloads")
    os.makedirs(download_dir, exist_ok=True)
    LOGGER.info("Working directory ready -> %s", download_dir)
