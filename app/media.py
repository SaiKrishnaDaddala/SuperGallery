"""Video probing and frame grabs through PyAV, each in a short-lived helper process with a time limit."""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

AVAILABLE = importlib.util.find_spec("av") is not None
_WORKER = str(Path(__file__).with_name("media_worker.py"))


def _run(args, timeout):
    return subprocess.run([sys.executable, "-I", _WORKER, *args], capture_output=True, timeout=timeout, check=True).stdout


def probe(path: str):
    """(width, height, duration) or None when the file can't be read."""
    if not AVAILABLE:
        return None
    try:
        d = json.loads(_run(["probe", path], 20) or b"{}")
        return d.get("width"), d.get("height"), d.get("duration")
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def frame(path: str, seconds: float, fit: int, timeout: int = 30) -> Image.Image | None:
    """First frame at or after `seconds`, scaled to fit a fit x fit box; None if there is none."""
    if not AVAILABLE:
        return None
    try:
        out = _run(["frame", path, f"{max(0.0, float(seconds)):.3f}", str(int(fit))], timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    with Image.open(io.BytesIO(out)) as image:
        return image.convert("RGB")
