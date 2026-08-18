<p align="center">
  <img src="../bot/assets/arcdlbot_profile_icon.png" alt="Arc Downloader" width="120" />
</p>

# Arc Downloader (Part of the [Team Arc](https://telegram.dog/ArcBotz))

A Telegram bot that fetches and delivers media — right into any chat, or straight through inline mode — backed by the [Arc API](https://portal.arcmusic.fun).

Send it a song name, a YouTube/Spotify/SoundCloud link, or a link from Instagram, Facebook, Threads, Bluesky, TikTok, or Twitter/X, and it downloads, prepares, and sends the file back to you. In group and private chats it replies directly; in inline mode (`@YourBot <query>`) it delivers into whatever chat you're typing in, no need to leave the conversation.

## Features

- **Search & direct links** — type a song name for top matches, or paste a supported link to fetch it straight away
- **Playlists** — YouTube and Spotify playlist links are listed with paginated, tap-to-download results
- **Inline mode** — `@YourBot <query>` fetches and delivers the result directly into any chat, auto-starting the moment a result is picked
- **Social media downloads** — Instagram, Facebook, Threads, Bluesky, TikTok, and Twitter/X media links
- **Automatic audio normalization** — YouTube downloads are probed and transcoded (via `ffmpeg`) to a consistent, playable format with embedded thumbnail and metadata
- **Clone this bot** — any user can spin up their own copy of Arc Downloader, running under their own bot account, straight from `/start`; see [Clone feature](#clone-feature) below
- **Admin tools** — `/stats` and `/broadcast` for bot owners and sudo users
- **MongoDB-backed user tracking** — minimal footprint, used only for broadcast targeting and keeping cloned bots alive across restarts

## How it works

```
User message / inline query
        │
        ▼
  Classifier (bot/utils/classifier.py)
   detects: search | youtube | spotify | soundcloud | social link
        │
        ▼
  Arc API (bot/dl/api_client.py)
   resolves the query to a CDN url
        │
        ▼
  Downloader (bot/dl/downloader.py)
   fetches the file, transcodes if needed, attaches thumbnail + caption
        │
        ▼
  Delivered to the chat (private/group) or edited straight
  into place for inline results
```

Inline deliveries don't need to relay through any other chat to obtain a `file_id` — the freshly downloaded file is uploaded directly over MTProto and used to edit the placeholder result in place.

## Clone feature

Anyone talking to the main bot can create their own independent copy of Arc Downloader:

1. Tap **🤖 Clone this bot** on `/start` and follow Telegram's managed-bot creation flow.
2. Arc Downloader receives the new bot's token, launches a `Client` for it, wires up the same search/download/inline handlers the main bot uses, and applies shared branding (profile photo, short description, description).
3. The clone is fully independent — it fetches from the same Arc API and behaves exactly like the main bot — and is owned by whoever created it.
4. Owners manage their clones any time with `/mybot`: start, stop, or delete each one.
5. Every clone is recorded in MongoDB, so it's automatically relaunched if the main bot restarts.

Cloning is a main-bot-only capability — a clone can't be used to create further clones or manage anyone else's.

Inline mode and inline feedback are **not** enabled automatically on a freshly cloned bot. Telegram doesn't expose an API for a manager bot to toggle another bot's `/setinline` or `/setinlinefeedback` settings — those remain BotFather-only, owner-gated switches (confirmed against the [Managed bots API](https://core.telegram.org/api/bots/managed-bots), which only exposes token export and access-restriction controls). Arc Downloader tells every new clone owner about this in the "clone launched" message and points them to the same two BotFather commands described below.

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) and `ffprobe` available on `PATH`
- A MongoDB instance (local or hosted, e.g. MongoDB Atlas)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- API credentials for `api_id` / `api_hash` from [my.telegram.org](https://my.telegram.org)
- Access key for a deployed instance of the [Arc API](https://github.com/tusar404/ArcMusic)

## Local development

```bash
git clone https://github.com/tusar404/ArcDLBot.git
cd ArcDLBot

pip3 install -U -r requirements.txt

cp sample.env .env
vi .env

python3 -m bot
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `API_ID` | Yes | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Yes | Telegram API hash from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather) |
| `API_URL` | Yes | Base URL of your deployed Arc API instance |
| `API_KEY` | Yes | API key for the Arc API |
| `MONGO_URI` | Yes | MongoDB connection string |
| `OWNER_ID` | Yes | Your numeric Telegram user ID |
| `SUDO_USERS` | No | Comma-separated numeric user IDs with admin command access, in addition to `OWNER_ID` |

### Enable inline delivery in @BotFather

Inline mode itself, and inline feedback, are settings Telegram only lets a bot's owner change — there's no Bot API or MTProto method for a third party (including a manager bot) to flip them, so this step can't be scripted:

1. Message [@BotFather](https://t.me/BotFather)
2. `/setinline` → select your bot → set any placeholder text
3. `/setinlinefeedback` → select your bot → `100%`

Without step 3, Telegram won't notify the bot when an inline result is chosen, and delivery will only happen if the user manually taps the Retry button. This applies to the main bot and to every cloned bot individually — each clone owner needs to do it once for their own bot.

### Enable the clone feature in @BotFather

Cloning relies on Telegram's managed-bot (Business Bots) capability:

1. Message [@BotFather](https://t.me/BotFather)
2. Enable managed bots for your bot so it can request and receive tokens for bots created on its behalf

## Project structure

```
bot/
├── assets/        # profile photo used to brand the main bot and every clone
├── core/          # client, config, mongo, clone manager, filesystem setup
├── dl/            # Arc API client, download/delivery pipeline, ffmpeg helpers
├── handlers/      # thin Pyrogram entry points only — one file per update type,
│                  # each declaring a HandlerRegistry and delegating to bot/utils
└── utils/         # caching, classification, keyboards, text, formatting, and
                   # every handler's business logic (search dispatch, inline
                   # result building, clone UI, broadcast, onboarding, stats)
```

Each handler module (`bot/handlers/*.py`) only wires Pyrogram update types to plain functions via a small `HandlerRegistry` — see `bot/utils/registry.py`. All actual logic lives in `bot/utils/`, so a handler file is never more than the registration boilerplate plus a couple of lines forwarding to a utility function.

## License

MIT — see [LICENSE](LICENSE).
