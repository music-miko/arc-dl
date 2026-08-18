# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
from contextlib import suppress

from pyrogram import idle

from . import LOGGER, __bot_name__, __version__, app, mongo, setup_directories, yt_api
from .core.clones import clones


async def main() -> None:
    LOGGER.info("Starting %s v%s...", __bot_name__, __version__)

    setup_directories()
    await mongo.connect()
    await yt_api.get_session()

    await app.start()

    from . import handlers

    LOGGER.info("All modules loaded. Bot is up and running.")

    await clones.load_all()

    try:
        await idle()
    finally:
        LOGGER.info("Shutting down %s...", __bot_name__)
        for bot_id in list(clones.active):
            with suppress(Exception):
                await clones.stop(bot_id)
        with suppress(Exception):
            await app.stop()
        with suppress(Exception):
            await yt_api.close()
        with suppress(Exception):
            await mongo.close()
        LOGGER.info("Arc Downloader stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
