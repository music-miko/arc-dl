# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Core: everything about starting the bot up — settings, the Kurigram
client, the Mongo connection, and the local directories it needs. Handlers
and the dl layer import from here rather than reaching into these files
directly.
"""

from .client import app
from .config import config
from .dirs import setup_directories
from .mongo import mongo
