"""ffprobe / ffmpeg helpers used to guarantee YouTube audio is sent as mp3."""

import asyncio
import json
import logging
import os

logger = logging.getLogger("arcdl.dl.ffmpeg")


async def probe_codec(path: str) -> str | None:
    """Returns the audio codec name (e.g. 'mp3', 'aac', 'opus') via ffprobe,
    or None if the file can't be probed."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name", "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(out.decode())
        streams = data.get("streams") or []
        return streams[0].get("codec_name") if streams else None
    except Exception:
        return None


async def ensure_mp3(input_path: str) -> str:
    """Returns a path to an mp3 version of `input_path`. If the file is
    already mp3-encoded, returns it unchanged. Otherwise transcodes with
    ffmpeg and returns the new path (leaving the original in place)."""
    codec = await probe_codec(input_path)
    if codec == "mp3":
        return input_path

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}.mp3"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-acodec", "libmp3lame", "-b:a", "192k",
        output_path,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg conversion failed: {stderr.decode()[-500:]}")

    return output_path
