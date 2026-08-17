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
        self.bot_id = int(self.bot_token.split(":")[0]) if ":" in self.bot_token else 0

        self.api_url = os.getenv("API_URL", "https://api.arcmusic.fun").rstrip("/")
        self.api_key = os.getenv("API_KEY", "")

        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")

        # Private channel/group the bot (and any clone bots) must be admin in.
        # Required for inline delivery: Telegram forbids uploading a *new* file
        # when editing an inline message — only a previously-uploaded file_id or
        # a URL is accepted. So inline results are first sent here to obtain a
        # reusable file_id, which is then used to edit the inline message.
        self.log_channel_id = int(os.getenv("LOG_CHANNEL_ID", "0"))

        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        self.sudo_users = {
            int(x) for x in os.getenv("SUDO_USERS", "").replace(" ", "").split(",") if x
        }
        self.sudo_users.add(self.owner_id)


config = Config()
