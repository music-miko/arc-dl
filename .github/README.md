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

For inline results to start downloading automatically the moment a user picks one, inline feedback must be turned on:

1. Message [@BotFather](https://t.me/BotFather)
2. `/setinlinefeedback` → select your bot → `100%`

Without this, Telegram won't notify the bot when an inline result is chosen, and delivery will only happen if the user manually taps the Retry button.

### Enable the clone feature in @BotFather

Cloning relies on Telegram's managed-bot (Business Bots) capability:

1. Message [@BotFather](https://t.me/BotFather)
2. Enable managed bots for your bot so it can request and receive tokens for bots created on its behalf

## Project structure

```
bot/
├── core/          # client, config, mongo, clone manager, filesystem setup
├── dl/            # Arc API client, download/delivery pipeline, ffmpeg helpers
├── handlers/      # message, inline, callback, clone, and admin command handlers
└── utils/         # caching, classification, keyboards, text, formatting
```

## License

MIT — see [LICENSE](LICENSE).
