# ArcDLBot

A Telegram bot that fetches and delivers media from a link or a search,
powered by Arc API.

Live bot: [@ArcDLBot](https://t.me/ArcDLBot)
Updates: [@ArcUpdates](https://t.me/ArcUpdates) · Chat: [@ArcChatz](https://t.me/ArcChatz)

## Getting an API key

This bot is just an HTTP client of Arc API — it doesn't talk to
YouTube/Spotify/SoundCloud/social platforms itself. Get your own
`API_KEY` from **[portal.arcmusic.fun](https://portal.arcmusic.fun)**
and set it (along with `API_URL`, if you're not using the default
`https://api.arcmusic.fun`) in your `.env` file — see `.env.example`.

## Features

- **Search by name** — send a song name and get the top matches as
  buttons; tap one to get the mp3.
- **Direct links** — paste a YouTube video, Spotify track, or SoundCloud
  link and it's fetched straight away.
- **Social platforms** — Instagram, Facebook, Threads, Bluesky, TikTok,
  and Twitter/X links are fetched and sent as-is.
- **Playlists** — paste a YouTube or Spotify playlist link to get every
  track listed with Prev/Next pagination; tapping a track downloads just
  that one.
- **Inline mode** — `@ArcDLBot <song name or link>` in any chat sends the
  media directly into that chat. No extra taps, no bot buttons, no
  private-chat hop.
- **Auto mp3 conversion** — YouTube audio is always delivered as a proper
  mp3, transcoded automatically if the source isn't already mp3-encoded.
- **Named downloads** — files arrive named after their actual title, not
  a random ID.
- **Admin tools** — `/stats` for uptime and user count, `/broadcast`
  (reply to a message) to message every user who's started the bot.

## Commands

| Command | Description |
| --- | --- |
| `/start` | Welcome message and quick guide |
| `/privacy` | How the bot handles your data |
| `/stats` | Uptime and user count (admins only) |
| `/broadcast` | Reply to a message to send it to every user (admins only) |
