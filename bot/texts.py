START_TEXT = """👋 **Hey, I'm {bot_name}!**

I fetch and send media as **{bot_name}** — straight from a link or a search, right here in this chat.

**Send me:**
• A song **name** → I'll show the top matches, tap one to get it
• A **YouTube / Spotify / SoundCloud** link → I'll fetch it directly
• A **playlist** link → I'll list its tracks, tap any one to download
• An **Instagram / Facebook / Threads / TikTok / Twitter (X) / Bluesky** link → I'll fetch the media in it

**Inline mode:** type `@{bot_username} <song name or link>` in *any* chat — results appear right there, no need to open a private chat with me.

Use /privacy to see how I handle your data.
"""

PRIVACY_TEXT = """🔒 **Privacy**

• I store your Telegram user ID, first name and username only so I can reach you with important updates — no messages or search history are kept.
• Links/song names you send are forwarded to the downloader API purely to fetch the file; they aren't logged anywhere by this bot.
• Downloaded files are deleted from this server right after being sent to you.

Nothing here is a substitute for reading the terms of the services you're downloading from — please respect copyright and each platform's own rules.
"""

GROUP_REDIRECT_TEXT = "⚠️ Downloads only work in a private chat with me — tap below to open one."

EXPIRED_TEXT = "⌛ This result has expired. Please search again."
