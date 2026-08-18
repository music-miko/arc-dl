# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import os

from .. import LOGGER


def setup_directories() -> None:
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    LOGGER.info("Working directory ready -> %s", download_dir)
