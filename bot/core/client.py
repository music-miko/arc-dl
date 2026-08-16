"""
The single shared Kurigram `Client` instance every handler registers
against. Nothing else in this file — the actual startup sequence (mongo
connect, directory setup, handler import, `app.run()`) lives in
`bot/__main__.py`.
"""

from pyrogram import Client

from .config import config

app = Client(
    "arcdl",
    api_id=config.api_id,
    api_hash=config.api_hash,
    bot_token=config.bot_token,
)
