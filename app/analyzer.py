"""Per-photo analysis: dimensions, EXIF date, perceptual hashes, sharpness and brightness."""
import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from . import db
from .config import ANALYZE_WORKERS, DECODABLE

log = logging.getLogger("supergallery")

Image.MAX_IMAGE_PIXELS = 400_000_000
try:  # iPhone photos
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001 - optional dependency
    pass

EXIF_IFD = 0x8769
DATE_ORIGINAL = 36867
DATE_TIME = 306
MAKE = 0x010F

CHAT = re.compile(r"whatsapp|telegram|instagram|facebook|messenger|snapchat|wechat|signal|twitter|reddit|"
                  r"tiktok|pinterest|sharechat|/memes?/|/stickers?/|/forwarded/", re.I)
CHAT_NAME = re.compile(r"^(img|vid|stk|null)-\d{8}-wa\d+|^fb_img_|^received_|^inshot_|^snapchat-|^telegram", re.I)
SHOT = re.compile(r"screenshot|screen[ _-]?shot|screen[ _-]?capture|scrnli|/screenshots?/", re.I)
CACHE = re.compile(r"/\.thumbnails?/|/\.thumbdata|/\.cache/", re.I)
PHONE_TRASH = re.compile(r"/\.trashed-|/\.trash/|/\.recycle(bin)?/|/\.trashbin/", re.I)
PHONE_WIDTHS = {640, 720, 750, 828, 1080, 1125, 1170, 1179, 1242, 1284, 1290, 1440, 1536, 1600, 2048}

# Bump when classify() changes: stored photos are re-sorted from saved metadata (no re-decoding).
CLASSIFY_VERSION = "3"
# Category keys (keep in sync with queries.PHOTO_KINDS)
KINDS = ("camera", "chat", "web", "screenshot", "document", "blurry", "dark", "lowq", "tiny", "cache",
         "phonetrash", "other")


def classify(path: str, w: int, h: int, size: int, make: str | None, blur: float, bright: float, sat: float) -> str:
    """Rule-based photo category from path, metadata and pixel statistics (no cloud, runs on the NAS)."""
    w, h, size = w or 0, h or 0, size or 0
    blur = 9999.0 if blur is None else blur
    bright = 128.0 if bright is None else bright
    sat = 100.0 if sat is None else sat
    px = w * h
    name = path.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if PHONE_TRASH.search(path):
        return "phonetrash"  # already deleted on the phone, still sitting in the backup
    if CACHE.search(path):
        return "cache"  # thumbnails the phone / apps regenerate by themselves
    if px < 40_000:
        return "tiny"
    if SHOT.search(path):
        return "screenshot"
    ar = max(w, h) / max(1, min(w, h))
    if not make and ext == "png" and min(w, h) in PHONE_WIDTHS and 1.6 <= ar <= 2.4:
        return "screenshot"
    if not make and (CHAT.search(path) or CHAT_NAME.search(name) or ext == "gif"):
        return "chat"
    if bright < 18:
        return "dark"
    if blur < 40 and px >= 250_000:
        return "blurry"
    if sat < 22 and bright > 150 and blur > 250:
        return "document"
    if not make and ext in ("jpg", "jpeg", "webp") and px < 1_300_000 and size < 350_000:
        return "web"  # small camera-less image: typically downloaded or saved from the web / apps
    if px < 1_000_000 or (not make and ext in ("jpg", "jpeg") and px and size / px < 0.06):
        return "lowq"
    return "camera" if make else "other"


def reclassify_all():
    """Re-sort already analysed photos with the current rules, using stored metadata only."""
    if db.kv_get("classify_version") == CLASSIFY_VERSION:
        return
    c = db.conn()
    rows = c.execute("SELECT id, path, width, height, size, make, blur, bright, sat FROM files "
                     "WHERE cat='image' AND analyzed=1").fetchall()
    out = [(classify(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]), r[0]) for r in rows]
    bad = c.execute("SELECT id, path FROM files WHERE cat='image' AND analyzed=-1").fetchall()
    out += [("phonetrash" if PHONE_TRASH.search(r[1]) else "cache" if CACHE.search(r[1]) else "other", r[0])
            for r in bad]
    with db.tx() as t:
        t.executemany("UPDATE files SET kind=? WHERE id=?", out)
    db.kv_set("classify_version", CLASSIFY_VERSION)
    log.info("re-sorted %s photos into categories (rules v%s)", len(out), CLASSIFY_VERSION)


def _to_int64(bits: np.ndarray) -> int:
    v = int.from_bytes(np.packbits(bits.astype(np.uint8)).tobytes(), "big")
    return v - (1 << 64) if v >= (1 << 63) else v


def _exif_make(im: Image.Image) -> str | None:
    try:
        v = im.getexif().get(MAKE)
        return (str(v).replace(chr(0), "").strip()[:40] or None) if v else None
    except Exception:  # noqa: BLE001
        return None


def _exif_ts(im: Image.Image) -> float | None:
    try:
        ex = im.getexif()
        raw = ex.get_ifd(EXIF_IFD).get(DATE_ORIGINAL) or ex.get(DATE_TIME)
        if not raw:
            return None
        d = dt.datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
        return d.timestamp() if 1971 < d.year < 2100 else None
    except Exception:  # noqa: BLE001 - corrupt EXIF is common
        return None


def analyze(path: str):
    with Image.open(path) as im:
        w, h = im.size
        taken = _exif_ts(im)
        make = _exif_make(im)
        im.draft("RGB", (512, 512))  # JPEG decodes at reduced scale: much faster
        rgb = im.convert("RGB")
    rgb.thumbnail((512, 512))
    hsv = np.asarray(rgb.resize((64, 64)).convert("HSV"), dtype=np.float32)
    sat = float(hsv[..., 1].mean())
    g = rgb.convert("L")
    a = np.asarray(g, dtype=np.float32)
    # Sharpness: variance of the Laplacian (low = blurry).
    lap = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    blur = float(lap.var()) if lap.size else 0.0
    bright = float(a.mean())
    r = np.asarray(g.resize((9, 8), Image.BILINEAR), dtype=np.int16)
    c = np.asarray(g.resize((8, 9), Image.BILINEAR), dtype=np.int16)
    ha = _to_int64((r[:, 1:] > r[:, :-1]).flatten())
    hb = _to_int64((c[1:, :] > c[:-1, :]).flatten())
    return w, h, ha, hb, taken, blur, bright, make, sat


def _safe(row):
    try:
        return analyze(row[1])
    except Exception:  # noqa: BLE001 - unreadable/corrupt image
        return None


def analyze_images(task):
    c = db.conn()
    rows = c.execute("SELECT id, path, ext, size FROM files WHERE cat='image' AND analyzed=0").fetchall()
    rows = [r for r in rows if r[2] in DECODABLE] + [r for r in rows if r[2] not in DECODABLE]
    task.progress(0, len(rows), stage="Analyzing photos (dates, similarity, sharpness)")
    done = 0
    with ThreadPoolExecutor(ANALYZE_WORKERS) as pool:
        for i in range(0, len(rows), 400):
            part = rows[i:i + 400]
            ok, bad = [], []
            for row, res in zip(part, pool.map(lambda r: _safe(r) if r[2] in DECODABLE else None, part)):
                if res is None:
                    bad.append((row[0],))
                else:
                    w, h, ha, hb, taken, blur, bright, make, sat = res
                    kind = classify(row[1], w, h, row[3], make, blur, bright, sat)
                    ok.append((w, h, ha, hb, taken, blur, bright, make, sat, kind, row[0]))
            with db.tx() as t:
                t.executemany("""UPDATE files SET analyzed=1, width=?, height=?, ha=?, hb=?,
                                 ts=COALESCE(?, ts), blur=?, bright=?, make=?, sat=?, kind=? WHERE id=?""", ok)
                t.executemany("UPDATE files SET analyzed=-1, kind='other' WHERE id=?", bad)
            done += len(part)
            task.progress(done)
    log.info("photo analysis finished: %s photos analysed", done)
    db.kv_set("classify_version", CLASSIFY_VERSION)
    return {"analyzed": done}
