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

import logging

from . import __version__
from .core import app, mongo, setup_directories

logger = logging.getLogger("arcdl.main")


def main() -> None:
    logger.info("Starting Arc-DL v%s...", __version__)

    setup_directories()
    app.loop.run_until_complete(mongo.connect())

    from . import handlers  # noqa: F401  (import registers all handlers)

    logger.info("All modules loaded. Connecting to Telegram...")
    app.run()
    logger.info("Arc-DL stopped.")


if __name__ == "__main__":
    main()
