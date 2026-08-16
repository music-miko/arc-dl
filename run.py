"""
Entrypoint. Importing the handler modules is what actually registers each
@app.on_message / @app.on_callback_query / @app.on_inline_query — they all
decorate the shared `app` instance from bot.client.
"""

from bot.client import app
from bot.handlers import admin, callback, inline, search, start  # noqa: F401

if __name__ == "__main__":
    print("Starting YT-API downloader bot...", flush=True)
    app.run()
