# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


START_TEXT = """Hi, I'm {bot_name}.

I fetch and send media from a link or a search, right here in this chat.

Send me:
- A song name — I'll show the top matches, tap one to get it
- A YouTube, Spotify, or SoundCloud link — I'll fetch it directly
- A playlist link — I'll list its tracks, tap any one to download
- An Instagram, Facebook, Threads, TikTok, Twitter (X), or Bluesky link — I'll fetch the media in it

Inline mode: type @{bot_username} <song name or link> in any chat — results
are sent directly, no extra taps needed.

Use /privacy to see how I handle your data.

This bot is open source: github.com/tusar404/ArcDLBot
"""

CLONE_HINT_TEXT = (
    "\nWant your own copy of this bot, running under your own bot account? "
    "Tap Clone this bot below.\n"
    "Manage the bots you've cloned any time with /mybot."
)

PRIVACY_TEXT = """Privacy

- I store your Telegram user ID, first name, and username only so I can reach you with important updates — no messages or search history are kept.
- Links and song names you send are forwarded to Arc API purely to fetch the file; they aren't logged anywhere by this bot.
- Downloaded files are deleted from this server right after being sent to you.

This isn't a substitute for reading the terms of the services you're downloading from — please respect copyright and each platform's own rules.
"""

NO_CLONES_TEXT = "You haven't cloned this bot yet. Tap Clone this bot in /start to create one."
YOUR_CLONES_TEXT = "Your cloned bots:"

NOT_YOUR_BOT_TEXT = "This isn't your bot."
CLONE_STOPPED_TEXT = "Bot stopped."
CLONE_STARTED_TEXT = "Bot started."
CLONE_START_FAILED_TEXT = "Couldn't start that bot — its token may have been revoked."
CLONE_DELETED_TEXT = "Bot deleted."

CLONE_SETUP_FAILED_TEXT = "Something went wrong setting up your cloned bot. Please try again with /start."
CLONE_LAUNCHED_TEXT = (
    "Your bot @{username} is live and works just like this one for search, links, and playlists.\n\n"
    "One manual step to finish: message @BotFather → /setinline → choose @{username} → set a "
    "placeholder, then /setinlinefeedback → @{username} → 100%. Telegram only lets a bot's owner "
    "turn these on, so this can't be automated on your behalf.\n\n"
    "Manage your clones anytime with /mybot."
)

EXPIRED_TEXT = "This result has expired. Please search again."

PROCESSING_TEXT = "Processing this..."
DOWNLOADING_TEXT = "Downloading..."
SENDING_TEXT = "Sending..."
STARTING_TEXT = "Starting download..."
NO_RESULTS_TEXT = "No results found."
UNSUPPORTED_LINK_TEXT = (
    "I don't recognize that link. I support YouTube, Spotify, SoundCloud, "
    "Instagram, Facebook, Threads, Bluesky, TikTok, and Twitter/X links, "
    "or just send me a song name."
)
