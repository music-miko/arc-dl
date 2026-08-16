# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.api_id = int(os.getenv("API_ID", "0"))
        self.api_hash = os.getenv("API_HASH", "")
        self.bot_token = os.getenv("BOT_TOKEN", "")

        self.api_url = os.getenv("API_URL", "https://api.arcmusic.fun").rstrip("/")
        self.api_key = os.getenv("API_KEY", "")

        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")

        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        self.sudo_users = {
            int(x) for x in os.getenv("SUDO_USERS", "").replace(" ", "").split(",") if x
        }
        self.sudo_users.add(self.owner_id)


config = Config()
