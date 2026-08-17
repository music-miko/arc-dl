# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from .. import LOGGER
from . import admin, callback, clones, inline, search, start


def attach_shared_handlers(client) -> None:
    for module in (start, search, callback, inline):
        for handler_cls, func, filt in module.HANDLERS:
            client.add_handler(handler_cls(func, filt))


LOGGER.info("Handlers loaded -> start, search, callback, inline, admin, clones")
