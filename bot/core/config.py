# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
Global settings — strictly the things that are genuinely shared/secret
across the whole bot (Telegram credentials, the Arc API endpoint, Mongo's
connection URI, admins). Everything else (download paths, poll timings,
pagination sizes, the Mongo database name, ...) is a plain `self.xxx` on
the class that actually uses it, set directly in that file — no reason to
route those through here too.
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
        self.api_url = os.getenv("API_URL", "https://api.arcmusic.fun").rstrip("/")
        self.api_key = os.getenv("API_KEY", "")

        # --- Mongo (bot's own DB — user list for /broadcast, nothing else;
        # the database name itself lives in bot/core/mongo.py, the only
        # file that needs it) ---
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")

        # --- Admins ---
        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        self.sudo_users = {
            int(x) for x in os.getenv("SUDO_USERS", "").replace(" ", "").split(",") if x
        }
        self.sudo_users.add(self.owner_id)


config = Config()
