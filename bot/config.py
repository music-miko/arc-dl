import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Telegram ---
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    # --- YT-API (this bot is just a client of it, over plain HTTP) ---
    YT_API_BASE_URL = os.getenv("YT_API_BASE_URL", "https://api.arcmusic.fun").rstrip("/")
    YT_API_KEY = os.getenv("YT_API_KEY", "")

    # --- Mongo (bot's own DB — user list for /broadcast, nothing else) ---
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ytdlbot")

    # --- Admins ---
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
    SUDO_USERS = {
        int(x) for x in os.getenv("SUDO_USERS", "").replace(" ", "").split(",") if x
    }
    SUDO_USERS.add(OWNER_ID)

    # --- Misc ---
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    JOB_POLL_INTERVAL = float(os.getenv("JOB_POLL_INTERVAL", "2"))
    JOB_POLL_TIMEOUT = float(os.getenv("JOB_POLL_TIMEOUT", "180"))
    MAX_LIST_BUTTONS = int(os.getenv("MAX_LIST_BUTTONS", "20"))  # playlist button cap per message
    PLAYLIST_PAGE_SIZE = int(os.getenv("PLAYLIST_PAGE_SIZE", "8"))
    PROMO_TAG = os.getenv("PROMO_TAG", "@ArcUpdates")


config = Config()

os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
