"""
Global settings — strictly the things that are genuinely shared/secret
across the whole bot (Telegram credentials, the YT-API endpoint, Mongo,
admins). Everything else (download paths, poll timings, pagination sizes,
promo text, ...) is a plain `self.xxx` on the class that actually uses it,
set directly in that file — no reason to route those through here too.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        # --- Telegram ---
        self.api_id = int(os.getenv("API_ID", "0"))
        self.api_hash = os.getenv("API_HASH", "")
        self.bot_token = os.getenv("BOT_TOKEN", "")

        # --- Arc API (this bot is a client of it, over plain HTTP) ---
        self.yt_api_base_url = os.getenv("YT_API_BASE_URL", "https://api.arcmusic.fun").rstrip("/")
        self.yt_api_key = os.getenv("YT_API_KEY", "")

        # --- Mongo (bot's own DB — user list for /broadcast, nothing else) ---
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_db_name = os.getenv("MONGO_DB_NAME", "arcdl")

        # --- Admins ---
        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        self.sudo_users = {
            int(x) for x in os.getenv("SUDO_USERS", "").replace(" ", "").split(",") if x
        }
        self.sudo_users.add(self.owner_id)


config = Config()
