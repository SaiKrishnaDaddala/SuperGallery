"""Thumbnail / preview generation with an on-disk WebP cache."""
import hashlib
import io
import os
import shutil
import subprocess
import threading

from PIL import Image, ImageOps

from . import analyzer  # noqa: F401 - registers the HEIC opener
from .config import DECODABLE, THUMB_DIR, VIDEO_THUMB

_sem = threading.BoundedSemaphore(max(2, (os.cpu_count() or 4)))
FFMPEG = shutil.which("ffmpeg")


def _cache_path(path: str, st: os.stat_result, size: int) -> str:
    key = hashlib.sha1(f"{path}|{st.st_mtime}|{st.st_size}|{size}".encode()).hexdigest()
    return os.path.join(THUMB_DIR, key[:2], key + ".webp")


def _video_frame(path: str, size: int) -> Image.Image | None:
    if not FFMPEG:
        return None
    for seek in ("3", "0"):
        try:
            out = subprocess.run(
                [FFMPEG, "-v", "error", "-ss", seek, "-i", path, "-frames:v", "1",
                 "-vf", f"scale={size}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                capture_output=True, timeout=30, check=False).stdout
            if out:
                return Image.open(io.BytesIO(out))
        except (subprocess.TimeoutExpired, OSError):
            return None
    return None


def render(path: str, ext: str, size: int) -> str | None:
    """Return path to a cached WebP rendition of `path`, or None if it can't be rendered."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    out = _cache_path(path, st, size)
    if os.path.exists(out):
        return out
    with _sem:
        if os.path.exists(out):
            return out
        try:
            if ext in DECODABLE:
                im = Image.open(path)
                im.draft("RGB", (size, size))
                im = ImageOps.exif_transpose(im)
            elif ext in VIDEO_THUMB:
                im = _video_frame(path, size)
                if im is None:
                    return None
            else:
                return None
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
            im.thumbnail((size, size), Image.LANCZOS if size <= 512 else Image.BICUBIC)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            tmp = out + ".tmp"
            im.save(tmp, "WEBP", quality=80 if size <= 512 else 86, method=4)
            os.replace(tmp, out)
            return out
        except Exception:  # noqa: BLE001 - corrupt or unsupported file
            return None
