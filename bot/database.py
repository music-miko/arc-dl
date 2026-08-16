import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from .config import config

_client = AsyncIOMotorClient(config.MONGO_URI)
_db = _client[config.MONGO_DB_NAME]
users = _db["users"]


async def touch_user(user_id: int, first_name: str, username: str | None) -> None:
    """Upserts the user + updates last_seen. Called on every /start and
    every message so /broadcast always has an up-to-date audience."""
    await users.update_one(
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


async def all_user_ids() -> list[int]:
    cursor = users.find({}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


async def user_count() -> int:
    return await users.count_documents({})


async def remove_user(user_id: int) -> None:
    await users.delete_one({"_id": user_id})
