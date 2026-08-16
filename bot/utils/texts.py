# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""Static copy shown to users. Kept plain and to the point on purpose —
no per-platform emoji labels, just clear text."""

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
"""

PRIVACY_TEXT = """Privacy

- I store your Telegram user ID, first name, and username only so I can reach you with important updates — no messages or search history are kept.
- Links and song names you send are forwarded to Arc API purely to fetch the file; they aren't logged anywhere by this bot.
- Downloaded files are deleted from this server right after being sent to you.

This isn't a substitute for reading the terms of the services you're downloading from — please respect copyright and each platform's own rules.
"""

GROUP_REDIRECT_TEXT = "Downloads only work in a private chat with me — tap below to open one."

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
