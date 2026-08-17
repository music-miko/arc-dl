# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
import json
import os


async def probe_codec(path: str) -> str | None:
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
