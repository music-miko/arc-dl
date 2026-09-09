# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from .. import LOGGER
from ..core.client import app
from ..core.mongo import mongo
from ..dl.api_client import YTAPIError
from ..locale import text as t
from ..utils.classifier import classifier
from ..utils.helper import not_command_filter
from ..utils.search_flow import dispatch_query
from . import search_registry as registry


@registry.on(
    MessageHandler,
    (filters.private | filters.group) & filters.text & ~filters.via_bot & not_command_filter,
)
async def handle_text(client, message: Message):
    user = message.from_user
    lang = "en"
    if user:
        lang = await mongo.touch_user(user.id, user.first_name or "", user.username)

    query = message.text.strip()

    if message.chat.type != ChatType.PRIVATE and not classifier.url_re.search(query):
        return

    kind, value = classifier.classify(query)

    try:
        await dispatch_query(client, message, kind, value, lang)
    except YTAPIError as e:
        await message.reply_text(str(e))
    except Exception as e:
        LOGGER.exception("Unexpected error handling message from %s", message.chat.id)
        await message.reply_text(t("something_wrong_text", lang, error=e))


registry.attach(app)
