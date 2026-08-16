# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import re


def sanitize_filename(name: str, max_len: int = 150) -> str:
    name = name or "track"
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] or "track"


def duration_to_seconds(duration) -> int:
    if duration is None:
        return 0
    if isinstance(duration, (int, float)):
        return int(duration)
    try:
        parts = [int(p) for p in str(duration).strip().split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def truncate(text: str, length: int) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def guess_kind_from_ext(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext in {"mp3", "m4a", "aac", "ogg", "opus", "wav", "flac"}:
        return "audio"
    if ext in {"mp4", "mov", "mkv", "webm", "m3u8", "ts"}:
        return "video"
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"
    return "document"
