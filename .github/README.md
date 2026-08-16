# ArcDLBot(Part of the [Team Arc](https://telegram.dog/ArcBotz))

A Telegram bot that fetches and delivers media — right into any chat, or straight through inline mode — backed by the [Arc API](https://portal.arcmusic.fun).

Send it a song name, a YouTube/Spotify/SoundCloud link, or a link from Instagram, Facebook, Threads, Bluesky, TikTok, or Twitter/X, and it downloads, prepares, and sends the file back to you. In group and private chats it replies directly; in inline mode (`@YourBot <query>`) it delivers into whatever chat you're typing in, no need to leave the conversation.



## Features

- **Search & direct links** — type a song name for top matches, or paste a supported link to fetch it straight away
- **Playlists** — YouTube and Spotify playlist links are listed with paginated, tap-to-download results
- **Inline mode** — `@YourBot <query>` fetches and delivers the result directly into any chat, auto-starting the moment a result is picked
- **Social media downloads** — Instagram, Facebook, Threads, Bluesky, TikTok, and Twitter/X media links
- **Automatic audio normalization** — YouTube downloads are probed and transcoded (via `ffmpeg`) to a consistent, playable format with embedded thumbnail and metadata
- **Admin tools** — `/stats` and `/broadcast` for bot owners and sudo users
- **MongoDB-backed user tracking** — minimal footprint, used only for broadcast targeting

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
  Delivered to the chat (private/group) or relayed and
  edited into place (inline results)
```

Inline results can't have a freshly-uploaded file attached directly (Telegram only allows a `file_id` or a fetchable URL there), so inline deliveries are first uploaded to `LOG_CHANNEL` to obtain a `file_id`, which is then used to edit the placeholder message in place.

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) and `ffprobe` available on `PATH`
- A MongoDB instance (local or hosted, e.g. MongoDB Atlas)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- API credentials for `api_id` / `api_hash` from [my.telegram.org](https://my.telegram.org)
- Access key for a deployed instance of the [Arc API](https://github.com/tusar404/ArcMusic)
- A Telegram channel (with the bot added as admin) to use as `LOG_CHANNEL`

## Local development

```bash
git clone https://github.com/tusar404/ArcDLBot.git
cd ArcDLBot

pip3 install -U -r requirements.txt

cp sample.env .env
vi .env # Edit .env with your credentials

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
| `LOG_CHANNEL` | Yes | Channel ID the bot relays files through to deliver inline results (bot must be an admin there) |
| `OWNER_ID` | Yes | Your numeric Telegram user ID |
| `SUDO_USERS` | No | Comma-separated numeric user IDs with admin command access, in addition to `OWNER_ID` |

### Enable inline delivery in @BotFather

For inline results to start downloading automatically the moment a user picks one, inline feedback must be turned on:

1. Message [@BotFather](https://t.me/BotFather)
2. `/setinlinefeedback` → select your bot → `100%`

Without this, Telegram won't notify the bot when an inline result is chosen, and delivery will only happen if the user manually taps the Retry button.

## Project structure

```
bot/
├── core/          # client, config, mongo, filesystem setup
├── dl/            # Arc API client, download/delivery pipeline, ffmpeg helpers
├── handlers/      # message, inline, callback, and admin command handlers
└── utils/         # caching, classification, keyboards, text, formatting
```

## License

MIT — see [LICENSE](LICENSE).
