# YT-API Downloader Bot

A Telegram bot built as a **client of your YT-API deployment** — every
search/download goes over plain HTTP to your API's routes (`/youtube/v2/*`,
`/spotify/*`, `/soundcloud/*`). This repo has no scraping logic of its own.

## Features

- **Search by name** (private chat): send a song name → top 5 YouTube
  results as buttons → tap one to get the MP3.
- **Direct links**: paste a YouTube video, Spotify track, or SoundCloud
  link → downloaded straight away.
- **Playlists**: paste a YouTube or Spotify playlist link → its tracks are
  listed as buttons (capped at `MAX_LIST_BUTTONS`, default 20).
- **Inline mode**: `@YourBot song name` in *any* chat shows top-5 results.
  Tapping "⬇️ Download MP3" opens a private chat with the bot and starts
  the download there — **actual downloads only ever happen in private
  chat**, by construction (see "Why deep-link on inline mode?" below).
- **Auto mp3 conversion**: every file is probed with `ffprobe`; anything
  that isn't already mp3-encoded gets transcoded with `ffmpeg` before
  being sent.
- **Named downloads**: files are sent with the song's actual title as the
  filename/tags (`Song Name.mp3`), not a random ID.
- `/start`, `/privacy`, `/stats` (admins), `/broadcast` (admins, reply to
  a message to broadcast it to every user who has started the bot).

## Setup

1. **System dependency**: `ffmpeg` must be installed and on `PATH`
   (`apt install ffmpeg` on Debian/Ubuntu).
2. Get `API_ID` / `API_HASH` from <https://my.telegram.org>, and a
   `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).
3. In BotFather, enable inline mode for your bot: `/setinline`.
4. Copy `.env.example` to `.env` and fill it in — in particular
   `YT_API_BASE_URL` + `YT_API_KEY` should point at your running YT-API
   instance and a valid API key for it.
5. `pip install -r requirements.txt`
6. `python run.py`

## Project layout

```
bot/
  config.py       env-based settings
  client.py       the single shared pyrogram.Client instance
  api_client.py   HTTP wrapper around YT-API's routes (incl. job polling)
  downloader.py   fetches a track's 'cdn' url, ensures mp3, sends it
  ffmpeg_utils.py ffprobe / ffmpeg helpers
  actions.py      shared "resolve cached result -> download -> send" logic
  cache.py        in-memory token store backing result buttons
  database.py     Mongo-backed user list (for /broadcast)
  utils.py        link classification, filename sanitizing, etc.
  keyboards.py    inline keyboard builders
  texts.py        static copy
  handlers/
    start.py      /start (incl. deep-link handoff), /privacy
    admin.py      /stats, /broadcast
    search.py     private-chat message dispatcher (links + name search)
    callback.py   button presses on search/playlist results
    inline.py     inline query handler
run.py            entrypoint
```

## Design notes

### Why deep-link on inline mode instead of a direct download button?

When a user picks an inline result, Telegram delivers it into whatever
chat they were in — the bot is never told which chat that is, and usually
has no permission to post there anyway (Bot API deliberately doesn't
expose this for privacy reasons). So there's no reliable way to attach a
"download now" button to an inline result and have it actually work.

Instead, the inline button is a normal URL deep link:
`https://t.me/YourBot?start=dl_<token>`. Opening it starts a private chat
with the bot and immediately triggers the download there. This is also
exactly what naturally satisfies "downloads only happen in private chat" —
there's no other code path that can send a file.

### Result cache

Search/playlist buttons reference a short token (`dl:<token>`), not raw
video IDs/URLs directly, because Spotify playlist track URLs don't fit
in Telegram's 64-byte `callback_data` limit. The token → metadata mapping
lives in an in-memory dict (`bot/cache.py`). It's intentionally not a
database: losing these on a bot restart just means "please search again",
which is a fine failure mode here.

### SoundCloud response shape

`bot/handlers/search.py`'s SoundCloud branch reads the download result
defensively (`result.get("title") or result.get("name") or ...`) because
this repo doesn't have visibility into `SoundCloudDownloader.smart()`'s
exact return schema beyond `cdn` + `success`. If your SoundCloud results
come back with different field names, adjust that one block.
