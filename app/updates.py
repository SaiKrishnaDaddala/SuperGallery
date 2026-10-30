"""Tell the user when a newer SuperGallery release exists, and optionally ask Watchtower to install it.

Only the public "latest release" of the GitHub repository is fetched (version, date and notes); nothing about the
library is sent. Turn it off in Settings or with UPDATE_CHECK=0. The app never gets Docker access itself: one-click
updates need a separate Watchtower container (WATCHTOWER_URL + WATCHTOWER_TOKEN).
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

from fastapi import APIRouter, Body, HTTPException

from . import db, features

FEED = os.environ.get("UPDATE_FEED_URL", "https://api.github.com/repos/SaiKrishnaDaddala/SuperGallery/releases/latest")
EVERY = 12 * 3600
WATCHTOWER_URL = os.environ.get("WATCHTOWER_URL", "").rstrip("/")
WATCHTOWER_TOKEN = os.environ.get("WATCHTOWER_TOKEN", "")
WATCHTOWER_CONTAINER = os.environ.get("WATCHTOWER_CONTAINER", "supergallery")
router = APIRouter(prefix="/api/updates")
_lock = threading.Lock()


def _version(text):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def enabled():
    if os.environ.get("UPDATE_CHECK", "1") == "0":
        return False
    return db.kv_get("update_check", "1") != "0"


def _fetch():
    req = urllib.request.Request(FEED, headers={"Accept": "application/vnd.github+json",
                                                "User-Agent": f"SuperGallery/{features.VERSION} update-check"})
    with urllib.request.urlopen(req, timeout=8) as response:
        data = json.loads(response.read(1_000_000))
    return {"latest": (data.get("tag_name") or "").lstrip("v"), "name": data.get("name") or "",
            "notes": (data.get("body") or "")[:20_000], "url": data.get("html_url") or "",
            "published": data.get("published_at") or ""}


def status(force=False):
    current = features.VERSION
    base = {"current": current, "enabled": enabled(), "one_click": bool(WATCHTOWER_URL and WATCHTOWER_TOKEN)}
    if not base["enabled"]:
        return {**base, "available": False}
    with _lock:
        cached = json.loads(db.kv_get("update_info", "{}") or "{}")
        checked = float(db.kv_get("update_checked", 0) or 0)
        error = None
        if force or time.time() - checked > EVERY:
            try:
                cached = _fetch()
                db.kv_set("update_info", json.dumps(cached))
            except Exception:  # noqa: BLE001 - offline NAS or rate limit: keep the last answer
                error = "Couldn't reach GitHub to check for updates." if force else None
            checked = time.time()
            db.kv_set("update_checked", str(checked))
    latest = cached.get("latest", "")
    newer = bool(_version(latest) and _version(current) and _version(latest) > _version(current))
    return {**base, **cached, "available": newer, "checked": checked, "error": error}


@router.get("")
def get_status():
    return status()


@router.post("/check")
def check_now():
    return status(force=True)


@router.put("")
def set_enabled(body: dict = Body(...)):
    db.kv_set("update_check", "1" if body.get("enabled") else "0")
    return status()


@router.post("/apply")
def apply():
    """Ask a configured Watchtower to pull and restart SuperGallery. Without one, explain the manual steps."""
    if not (WATCHTOWER_URL and WATCHTOWER_TOKEN):
        raise HTTPException(409, "One-click updates need Watchtower. Redeploy with the latest image instead.")
    # Only this container is updated, never the rest of the NAS.
    req = urllib.request.Request(f"{WATCHTOWER_URL}/v1/update?container={urllib.parse.quote(WATCHTOWER_CONTAINER)}", method="POST",
                                 headers={"Authorization": "Bearer " + WATCHTOWER_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:  # noqa: BLE001 - Watchtower may close the connection while it restarts us
        pass
    return {"started": True}
