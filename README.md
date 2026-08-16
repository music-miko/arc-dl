# Arc-DL

A Telegram downloader bot built on **[Kurigram](https://github.com/KurimuzonAkuma/pyrogram)**,
powered by **Arc API** — every search/download goes over plain HTTP to
your Arc API deployment's routes (`/youtube/v2/*`, `/spotify/*`,
`/soundcloud/*`, and the social-platform routes). This repo has no
scraping logic of its own; it's purely a Telegram front end for Arc API.

A live example of this bot is running as [@ArcDLBot](https://t.me/ArcDLBot).
Updates and announcements are posted in [@ArcUpdates](https://telegram.dog/ArcUpdates).

## Features

- **Search by name** (private chat): send a song name → top 5 YouTube
  results as buttons → tap one to get the MP3.
- **Direct links**: paste a YouTube video, Spotify track, or SoundCloud
  link → downloaded straight away.
- **Social platforms**: Instagram, Facebook, Threads, Bluesky, TikTok,
  and Twitter/X links are fetched and sent as-is (no conversion).
- **Playlists**: paste a YouTube or Spotify playlist link → its tracks
  are listed as buttons with Prev/Next pagination.
- **Inline mode**: `@ArcDLBot song name` in *any* chat shows results.
  Each result carries a Download button that deep-links back into a
  private chat with the bot, which starts the download there. See
  "Why deep-link on inline mode?" below.
- **Auto mp3 conversion**: YouTube audio is probed with `ffprobe`;
  anything that isn't already mp3-encoded gets transcoded with `ffmpeg`
  before being sent.
- **Named downloads**: files are sent with the actual title as the
  filename/tags (`Song Name.mp3`), not a random ID.
- `/start`, `/privacy`, `/stats` (admins), `/broadcast` (admins, reply to
  a message to broadcast it to every user who has started the bot).

## Setup

1. **System dependency**: `ffmpeg` must be installed and on `PATH`
   (`apt install ffmpeg` on Debian/Ubuntu).
2. Get `API_ID` / `API_HASH` from <https://my.telegram.org>, and a
   `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).
3. In BotFather, enable inline mode for your bot: `/setinline`.
   (Inline *feedback* is **not** needed — see the design note below.)
4. Copy `.env.example` to `.env` and fill it in — in particular
   `YT_API_BASE_URL` + `YT_API_KEY` should point at your running Arc API
   instance and a valid API key for it.
5. `pip install -r requirements.txt`
6. `python -m bot`

## Project layout

```
bot/
  __init__.py       logging setup, package version
  __main__.py       entrypoint — `python -m bot`
  core/
    config.py        env-based settings (Telegram, Arc API, Mongo, admins)
    client.py         the single shared Kurigram Client instance
    mongo.py           Mongo connection + user-list operations
    dirs.py             sets up the bot's local working directories
  dl/
    api_client.py     HTTP wrapper around Arc API's routes (incl. job polling)
    downloader.py      fetches a track's 'cdn' url, ensures mp3, sends it
    ffmpeg.py            ffprobe / ffmpeg helpers
    actions.py             shared "resolve cached result -> download -> send" logic
  handlers/
    start.py          /start (incl. deep-link download handoff), /privacy
    admin.py            /stats, /broadcast
    search.py             private-chat message dispatcher (links + name search)
    callback.py             button presses on search/playlist results
    inline.py                  inline query handler
  utils/
    classifier.py     link/query classification
    cache.py            in-memory token store backing result buttons
    keyboards.py          inline keyboard builders
    texts.py                 static copy
    format.py                  filename sanitizing, duration parsing, etc.
```

Every directory is a proper package (`__init__.py` re-exports its public
pieces), so anything in the bot can be reached with a short import, e.g.:

```python
from bot.core import app, mongo, config
from bot.dl import run_download, yt_api
from bot.utils import cache, classifier, keyboards
```

## Design notes

### Why deep-link on inline mode instead of a direct download button?

When a user picks an inline result, Telegram delivers it into whatever
chat they were in — the bot is never told which chat that is, and
usually has no permission to post there anyway. Editing that result in
place afterwards (`on_chosen_inline_result` + `edit_inline_media`) is
possible in principle, but only if **inline feedback** is explicitly
turned on for the bot via BotFather (`/setinlinefeedback`) — most bots
don't have this enabled, and forgetting it makes inline mode look
completely broken (results just sit there forever).

So instead, every inline result carries a plain URL button that deep-links
back into a private chat: `https://t.me/ArcDLBot?start=dl_<token>`.
Opening it starts a private chat with the bot and immediately triggers the
download there. This needs no special BotFather configuration, and is
also exactly what naturally satisfies "downloads only happen in private
chat" — there's no other code path that can send a file.

### Result cache

Search/playlist buttons reference a short token (`dl:<token>`), not raw
video IDs/URLs directly, because Spotify playlist track URLs don't fit
in Telegram's 64-byte `callback_data` limit (deep-link start parameters
have a similar practical limit). The token → metadata mapping lives in an
in-memory store (`bot/utils/cache.py`). It's intentionally not a
database: losing these on a bot restart just means "please search again",
which is a fine failure mode here.

### SoundCloud response shape

`bot/handlers/search.py`'s SoundCloud branch reads the download result
defensively (`result.get("title") or result.get("name") or ...`) because
this repo doesn't have visibility into Arc API's SoundCloud downloader's
exact return schema beyond `cdn` + `success`. If your SoundCloud results
come back with different field names, adjust that one block.

### A note on aiohttp query parameters

Arc API's `/youtube/v2/download` route takes a boolean `isVideo` query
parameter. `aiohttp` (via `yarl`) refuses to serialize a raw Python
`bool` into a query string — it raises `TypeError: Invalid variable
type: value should be str, int or float, got False of type <class
'bool'>` before the request is even sent. `bot/dl/api_client.py`
normalizes any boolean query values to `"true"`/`"false"` strings for
exactly this reason; keep that in mind if you add new API calls that take
boolean parameters.
