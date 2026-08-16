# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
from contextlib import suppress

from pyrogram import idle

from . import LOGGER, __bot_name__, __version__, app, mongo, setup_directories, yt_api


async def main() -> None:
    LOGGER.info("Starting %s v%s...", __bot_name__, __version__)

    setup_directories()
    await mongo.connect()
    await yt_api.get_session()

    await app.start()

    from . import handlers

    LOGGER.info("All modules loaded. Bot is up and running.")

    try:
        await idle()
    finally:
        LOGGER.info("Shutting down %s...", __bot_name__)
        with suppress(Exception):
            await app.stop()
        with suppress(Exception):
            await yt_api.close()
        with suppress(Exception):
            await mongo.close()
        LOGGER.info("Arc-DL stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
