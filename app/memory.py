"""Give memory back when the AI models sit unused, and let background work yield the CPU."""
import ctypes
import gc
import logging
import os
import threading
import time

log = logging.getLogger("supergallery")
IDLE_SECONDS = float(os.environ.get("MODEL_IDLE_MINUTES", "10")) * 60
BACKGROUND_NICE = int(os.environ.get("BACKGROUND_NICE", "10"))


def trim():
    """Ask glibc to return freed heap pages to the OS (no-op elsewhere)."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def lower_priority():
    """Run the calling thread (and threads/processes it starts) at a lower CPU priority on Linux."""
    if BACKGROUND_NICE <= 0 or not hasattr(os, "setpriority"):
        return
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), BACKGROUND_NICE)
    except (OSError, AttributeError):
        pass


def _reaper():
    from . import people, visual_search
    while True:
        time.sleep(60)
        try:
            freed = [name for name, mod in (("search", visual_search), ("faces", people)) if mod.release_idle(IDLE_SECONDS)]
            if freed:
                trim()
                log.info("released idle models: %s", ", ".join(freed))
        except Exception:  # noqa: BLE001 - never let housekeeping stop
            log.exception("model release failed")


def start():
    if IDLE_SECONDS > 0:
        threading.Thread(target=_reaper, name="model-reaper", daemon=True).start()
