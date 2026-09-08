# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import os

from pyrogram import Client
from pyrogram.types import InputChatPhotoStatic

from .. import LOGGER
from .config import config
from .mongo import mongo


class CloneManager:
    def __init__(self):
        self.active: dict[int, Client] = {}
        self.profile_photo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "arcdlbot_profile_icon.png",
        )
        self.bot_short_description = (
            "Download music & media from YouTube, Spotify, SoundCloud, Instagram, "
            "TikTok, and more — right in Telegram."
        )
        self.bot_description = (
            "Send a song name, or paste a link from YouTube, Spotify, SoundCloud, "
            "Instagram, Facebook, Threads, TikTok, Twitter/X, or Bluesky — I'll fetch "
            "it and send it right back to you.\n\n"
            "Works in groups and inline too.\n\n"
            "This bot is a clone of Arc Downloader, built on the open-source Arc "
            "Downloader framework: github.com/tusar404/ArcDLBot"
        )

    async def load_all(self) -> None:
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
        try:
            await client.set_profile_photo(photo=InputChatPhotoStatic(self.profile_photo_path))
        except Exception:
            LOGGER.exception("Failed to set profile photo for clone bot_id=%s", client.me.id)

        try:
            await client.set_bot_info_short_description(self.bot_short_description)
            await client.set_bot_info_description(self.bot_description)
        except Exception:
            LOGGER.exception("Failed to set bio/description for clone bot_id=%s", client.me.id)


clones = CloneManager()
