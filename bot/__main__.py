# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Entrypoint — run the bot with `python -m bot`.

Order matters here:
1. Set up local directories the bot needs on disk.
2. Connect to MongoDB (and fail loudly, immediately, if that's broken).
3. Import the handlers package, which registers every @app.on_* decorator
   against the shared client from bot.core.
4. Hand off to app.run(), which connects to Telegram, idles, and cleans
   up on exit.
"""

from . import LOGGER, __bot_name__, __version__, app, mongo, setup_directories


def main() -> None:
    LOGGER.info("Starting %s v%s...", __bot_name__, __version__)

    setup_directories()
    app.loop.run_until_complete(mongo.connect())

    from . import handlers  # noqa: F401  (import registers all handlers)

    LOGGER.info("All modules loaded. Connecting to Telegram...")
    app.run()
    LOGGER.info("Arc-DL stopped.")


if __name__ == "__main__":
    main()
