# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

from .. import LOGGER
from ..locale import default_lang, normalize_lang
from .config import config


class MongoDB:
    def __init__(self):
        self.db_name = "arc"
        self.client = AsyncIOMotorClient(config.mongo_uri)
        self.db = self.client[self.db_name]
        self.users = self.db["users"]
        self.clones = self.db["clones"]
        self.lang_cache: dict[int, str] = {}

    async def connect(self) -> None:
        await self.client.admin.command("ping")
        LOGGER.info("Connected to MongoDB")

    async def close(self) -> None:
        self.client.close()
        LOGGER.info("MongoDB connection closed.")

    async def touch_user(self, user_id: int, first_name: str, username: str | None) -> str:
        doc = await self.users.find_one_and_update(
            {"_id": user_id},
            {
                "$set": {
                    "first_name": first_name,
                    "username": username,
                    "last_seen": datetime.datetime.utcnow(),
                },
                "$setOnInsert": {"joined_at": datetime.datetime.utcnow(), "lang": default_lang},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        lang = normalize_lang((doc or {}).get("lang"))
        self.lang_cache[user_id] = lang
        return lang

    async def get_lang(self, user_id: int) -> str:
        if user_id in self.lang_cache:
            return self.lang_cache[user_id]
        doc = await self.users.find_one({"_id": user_id}, {"lang": 1})
        lang = normalize_lang((doc or {}).get("lang"))
        self.lang_cache[user_id] = lang
        return lang

    async def set_lang(self, user_id: int, lang: str) -> str:
        lang = normalize_lang(lang)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"lang": lang}, "$setOnInsert": {"joined_at": datetime.datetime.utcnow()}},
            upsert=True,
        )
        self.lang_cache[user_id] = lang
        return lang

    async def all_user_ids(self) -> list[int]:
        cursor = self.users.find({}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def user_count(self) -> int:
        return await self.users.count_documents({})

    async def remove_user(self, user_id: int) -> None:
        await self.users.delete_one({"_id": user_id})
        self.lang_cache.pop(user_id, None)


    async def save_clone(self, bot_id: int, owner_id: int, username: str | None, token: str) -> None:
        await self.clones.update_one(
            {"_id": bot_id},
            {
                "$set": {"owner_id": owner_id, "username": username, "token": token},
                "$setOnInsert": {"created_at": datetime.datetime.utcnow()},
            },
            upsert=True,
        )

    async def all_clones(self) -> list[dict]:
        return [doc async for doc in self.clones.find({})]

    async def clone_count(self) -> int:
        return await self.clones.count_documents({})

    async def clones_for_owner(self, owner_id: int) -> list[dict]:
        return [doc async for doc in self.clones.find({"owner_id": owner_id})]

    async def get_clone(self, bot_id: int) -> dict | None:
        return await self.clones.find_one({"_id": bot_id})

    async def delete_clone(self, bot_id: int) -> None:
        await self.clones.delete_one({"_id": bot_id})


mongo = MongoDB()
