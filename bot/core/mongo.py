# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from .. import LOGGER
from .config import config


class MongoDB:
    def __init__(self):
        self.db_name = "arc"
        self.client = AsyncIOMotorClient(config.mongo_uri)
        self.db = self.client[self.db_name]
        self.users = self.db["users"]

    async def connect(self) -> None:
        await self.client.admin.command("ping")
        LOGGER.info("Connected to MongoDB -> database '%s'", self.db_name)

    async def close(self) -> None:
        self.client.close()
        LOGGER.info("MongoDB connection closed.")

    async def touch_user(self, user_id: int, first_name: str, username: str | None) -> None:
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
