from pyrogram import Client

from .config import config

app = Client(
    "ytdlbot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)
