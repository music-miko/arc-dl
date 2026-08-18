# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from .. import LOGGER
from ..core.client import app
from ..core.mongo import mongo
from ..dl.api_client import YTAPIError
from ..utils.classifier import classifier
from ..utils.registry import HandlerRegistry
from ..utils.search_flow import dispatch_query

registry = HandlerRegistry(__name__)

not_command_filter = filters.create(lambda _, __, m: not (m.text or "").startswith("/"))


@registry.on(MessageHandler, filters.private & filters.text & ~filters.via_bot & not_command_filter)
async def handle_text(client, message: Message):
    user = message.from_user
    if user:
        await mongo.touch_user(user.id, user.first_name or "", user.username)

    kind, value = classifier.classify(message.text)

    try:
        await dispatch_query(client, message, kind, value)
    except YTAPIError as e:
        await message.reply_text(str(e))
    except Exception as e:
        LOGGER.exception("Unexpected error handling message from %s", message.chat.id)
        await message.reply_text(f"Something went wrong: {e}")


registry.attach(app)
