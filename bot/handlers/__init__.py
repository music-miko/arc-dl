# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from .. import LOGGER
from . import admin, callback, clones, inline, search, start

SHARED_MODULES = (start, search, callback, inline)
MAIN_ONLY_MODULES = (admin, clones)


def attach_shared_handlers(client) -> None:
    for module in SHARED_MODULES:
        module.registry.attach(client)


LOGGER.info(
    "Handlers loaded -> %s",
    ", ".join(m.__name__.rsplit(".", 1)[-1] for m in SHARED_MODULES + MAIN_ONLY_MODULES),
)
