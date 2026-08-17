# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from .. import LOGGER
from . import admin, callback, clones, inline, search, start

_SHARED_MODULES = (start, search, callback, inline)


def attach_shared_handlers(client) -> None:
    """Wires up the same download/search/start handlers the main bot uses
    onto a cloned bot's Client. Deliberately excludes admin.py (main bot's
    own /stats, /broadcast) and handlers/clones.py (managing clones is a
    main-bot-only capability)."""
    for module in _SHARED_MODULES:
        for handler_cls, func, filt in module.HANDLERS:
            client.add_handler(handler_cls(func, filt))


LOGGER.info("Handlers loaded -> start, search, callback, inline, admin, clones")
