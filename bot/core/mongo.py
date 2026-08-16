"""
The bot's own Mongo database — just a user list so /broadcast has an
audience to send to. This has nothing to do with Arc API's own database;
the bot never touches that.
"""

import datetime
import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

from .config import config

logger = logging.getLogger("arcdl.core.mongo")


class MongoDB:
    def __init__(self):
        self.db_name = os.getenv("MONGO_DB_NAME", "arc")
        self.client = AsyncIOMotorClient(config.mongo_uri)
        self.db = self.client[self.db_name]
        self.users = self.db["users"]

    async def connect(self) -> None:
        """Pings Mongo so startup fails loudly (and immediately) if the
        connection is bad, instead of surfacing as a mystery error on the
        first /start."""
        await self.client.admin.command("ping")
        logger.info("Connected to MongoDB -> database '%s'", self.db_name)

    async def touch_user(self, user_id: int, first_name: str, username: str | None) -> None:
        """Upserts the user + updates last_seen. Called on every /start and
        every message so /broadcast always has an up-to-date audience."""
        await self.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "first_name": first_name,
                    "username": username,
                    "last_seen": datetime.datetime.utcnow(),
                },
                "$setOnInsert": {"joined_at": datetime.datetime.utcnow()},
            },
            upsert=True,
        )

    async def all_user_ids(self) -> list[int]:
        cursor = self.users.find({}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def user_count(self) -> int:
        return await self.users.count_documents({})

    async def remove_user(self, user_id: int) -> None:
        await self.users.delete_one({"_id": user_id})


mongo = MongoDB()
