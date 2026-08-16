# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Handlers: importing each of these modules is what actually registers its
@app.on_message / @app.on_callback_query / @app.on_inline_query
decorators against the shared `app` client from bot.core. `bot/__main__.py`
imports this package (and only this package) to wire everything up.
"""

from .. import LOGGER
from . import admin, callback, inline, search, start  # noqa: F401

LOGGER.info("Handlers loaded -> start, search, callback, inline, admin")
