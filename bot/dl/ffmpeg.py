# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

"""
ffprobe / ffmpeg helpers used to guarantee YouTube audio always reaches
Telegram in a format it can play as a proper audio message.

The source `downloader.py` hands in can be almost anything depending on
what Arc API had cached: an already-encoded mp3, a raw opus/webm stream
straight off a Telegram-cached message, or a direct CDN stream — and the
file's extension is not a reliable indicator of which one it actually
is. So this always identifies the real codec with ffprobe rather than
trusting the extension, and:

- leaves an already-mp3 file untouched,
- remuxes opus into an `.ogg` container with `-c copy` (no re-encode —
  Telegram plays ogg/opus audio messages natively, so this is instant
  and lossless), and
- transcodes anything else to mp3.

The output path is always built from a suffix that can't collide with
the input path, even when the input arrived with a misleading extension
(e.g. a raw opus stream saved as `*.mp3`) — ffmpeg refuses to write over
its own input, and silently reusing the input's exact name is exactly
how that happened before.
"""

import asyncio
import json
import os


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


async def ensure_audio(input_path: str) -> tuple[str, str]:
    """Returns (path, ext) for a Telegram-safe audio version of
    `input_path`. If the source is already mp3, returns it unchanged.
    Opus is remuxed into ogg; anything else is transcoded to mp3."""
    codec = await probe_codec(input_path)
    if codec == "mp3":
        return input_path, os.path.splitext(input_path)[1] or ".mp3"

    base, _ = os.path.splitext(input_path)

    if codec == "opus":
        output_path = f"{base}.arcconv.ogg"
        args = ["-y", "-i", input_path, "-vn", "-c:a", "copy", output_path]
    else:
        output_path = f"{base}.arcconv.mp3"
        args = ["-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-b:a", "192k", output_path]

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg conversion failed: {stderr.decode()[-500:]}")

    return output_path, os.path.splitext(output_path)[1]
