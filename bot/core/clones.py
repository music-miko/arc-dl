# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import os

from pyrogram import Client
from pyrogram.types import InputChatPhotoStatic

from .. import LOGGER
from .config import config
from .mongo import mongo

PROFILE_PHOTO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "arcdlbot_profile_icon.png")

BOT_SHORT_DESCRIPTION = (
    "Download music & media from YouTube, Spotify, SoundCloud, Instagram, "
    "TikTok, and more — right in Telegram."
)

BOT_DESCRIPTION = (
    "Send a song name, or paste a link from YouTube, Spotify, SoundCloud, "
    "Instagram, Facebook, Threads, TikTok, Twitter/X, or Bluesky — I'll fetch "
    "it and send it right back to you.\n\n"
    "Works in groups and inline too.\n\n"
    "This bot is a clone of @ArcDLBot, built on the open-source Arc-DL "
    "framework: github.com/tusar404/ArcDLBot"
)


class CloneManager:
    """Owns every currently-running cloned bot Client, and the Mongo-backed
    record of every clone ever created (so they can be relaunched on restart)."""

    def __init__(self):
        self.active: dict[int, Client] = {}

    async def load_all(self) -> None:
        """Relaunches every previously-created clone. Called once at startup,
        after the main app and the handlers package are both ready."""
        docs = await mongo.all_clones()
        for doc in docs:
            try:
                await self.spinup(doc["_id"], doc["token"], persist=False)
            except Exception:
                LOGGER.exception("Failed to relaunch clone bot_id=%s", doc["_id"])
        if docs:
            LOGGER.info("Relaunched %d/%d cloned bot(s).", len(self.active), len(docs))

    async def spinup(
        self, bot_id: int, token: str, *, owner_id: int | None = None,
        username: str | None = None, persist: bool = True,
    ) -> Client:
        """Starts a Client for this token and wires up the same handlers the
        main bot uses. Deferred import below avoids a circular import
        (bot.handlers imports bot.core at module load time; this only needs
        bot.handlers once the app is already fully running)."""
        if bot_id in self.active:
            return self.active[bot_id]

        client = Client(
            f"clone_{bot_id}",
            api_id=config.api_id,
            api_hash=config.api_hash,
            bot_token=token,
            in_memory=True,
        )

        from ..handlers import attach_shared_handlers
        attach_shared_handlers(client)

        await client.start()
        self.active[bot_id] = client

        if persist:
            await mongo.save_clone(bot_id, owner_id, username, token)

        return client

    async def stop(self, bot_id: int) -> None:
        client = self.active.pop(bot_id, None)
        if client:
            await client.stop()

    async def delete(self, bot_id: int) -> None:
        await self.stop(bot_id)
        await mongo.delete_clone(bot_id)

    async def set_branding(self, client: Client) -> None:
        """Applies the shared Arc-DL profile photo and bio to a freshly
        created clone. Best-effort — a clone still works fine without this."""
        try:
            await client.set_profile_photo(photo=InputChatPhotoStatic(PROFILE_PHOTO_PATH))
        except Exception:
            LOGGER.exception("Failed to set profile photo for clone bot_id=%s", client.me.id)

        try:
            await client.set_bot_info_short_description(BOT_SHORT_DESCRIPTION)
            await client.set_bot_info_description(BOT_DESCRIPTION)
        except Exception:
            LOGGER.exception("Failed to set bio/description for clone bot_id=%s", client.me.id)

clones = CloneManager()
