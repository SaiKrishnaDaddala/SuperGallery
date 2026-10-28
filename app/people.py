"""Local, incremental photo grouping. No images leave the NAS in this module."""
import hashlib
import itertools
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import os
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import HTTPException
from PIL import Image, ImageOps

from . import db, fileops, jobs, scope
from .config import DECODABLE

MODELS = Path(os.getenv("FACE_MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))
MODEL_HASHES = {
    "face_detection_yunet_2023mar.onnx": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    "face_recognition_sface_2021dec.onnx": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}
_lock = threading.RLock()
_engines = {}          # detection thread id -> (detector, recognizer); OpenCV models are not thread-safe
_verified = False
_last_used = 0.0
_pool = None
FACE_WORKERS = max(1, int(os.environ.get("FACE_WORKERS", "2")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS people(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL,
 prototype BLOB NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS face_index(
 file_id INTEGER PRIMARY KEY, path TEXT NOT NULL, mtime REAL NOT NULL, size INTEGER NOT NULL,
 state TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS faces(
 id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER NOT NULL, person_id INTEGER,
 embedding BLOB NOT NULL, crop BLOB NOT NULL, score REAL NOT NULL, ignored INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_faces_person ON faces(person_id, file_id);
CREATE INDEX IF NOT EXISTS ix_faces_file ON faces(file_id);
CREATE TRIGGER IF NOT EXISTS remove_deleted_photo_faces AFTER DELETE ON files BEGIN
 DELETE FROM people WHERE id IN (SELECT person_id FROM faces WHERE file_id=OLD.id)
   AND NOT EXISTS (SELECT 1 FROM faces WHERE person_id=people.id AND file_id!=OLD.id);
 DELETE FROM faces WHERE file_id=OLD.id;
 DELETE FROM face_index WHERE file_id=OLD.id;
END;
CREATE VIEW IF NOT EXISTS current_faces AS
 SELECT faces.*, f.owner, f.name AS filename, f.ts FROM faces
 JOIN face_index i ON i.file_id=faces.file_id
 JOIN files f ON f.id=i.file_id AND f.path=i.path AND f.mtime=i.mtime AND f.size=i.size;
"""


def init():
    db.conn().executescript(SCHEMA)


def engine():
    """This thread's face models, loaded on first use (each detection thread has its own pair)."""
    global _verified, _last_used
    _last_used = time.monotonic()
    key = threading.get_ident()
    with _lock:
        pair = _engines.get(key)
        if pair is None:
            import cv2
            if not _verified:
                for name, expected in MODEL_HASHES.items():
                    p = MODELS / name
                    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                        raise RuntimeError("Face models are missing or damaged. Reinstall the app's model bundle.")
                _verified = True
            # Photos are processed FACE_WORKERS at a time, so keep OpenCV's own threading small.
            cv2.setNumThreads(max(1, 2 // FACE_WORKERS))
            pair = (
                cv2.FaceDetectorYN.create(str(MODELS / next(iter(MODEL_HASHES))), "", (320, 320), 0.90, 0.3, 5000),
                cv2.FaceRecognizerSF.create(str(MODELS / "face_recognition_sface_2021dec.onnx"), ""),
            )
            _engines[key] = pair
    return pair


def release_idle(seconds):
    """Drop the face models after `seconds` without use; they reload on demand."""
    with _lock:
        if _engines and time.monotonic() - _last_used > seconds:
            _engines.clear()
            return True
    return False


def _detector_pool():
    # One long-lived pool keeps thread ids, and therefore loaded models, stable across batches.
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(FACE_WORKERS, thread_name_prefix="faces")
    return _pool


def _detect_ahead(rows):
    """Yield (row, future-or-None) in order while up to 2 x FACE_WORKERS photos are decoded and detected."""
    pool, source, pending = _detector_pool(), iter(rows), deque()

    def submit(row):
        return row, (pool.submit(detect, row["path"]) if row["ext"] in DECODABLE else None)

    for row in itertools.islice(source, 2 * FACE_WORKERS):
        pending.append(submit(row))
    while pending:
        item = pending.popleft()
        nxt = next(source, None)
        if nxt is not None:
            pending.append(submit(nxt))
        yield item


def detect(path):
    """Return bounded crops and normalized 128-dimensional embeddings; never identities."""
    import cv2
    detector, recognizer = engine()
    with Image.open(fileops.safe_path(path)) as source:
        source.draft("RGB", (1280, 1280))
        photo = ImageOps.exif_transpose(source).convert("RGB")
        photo.thumbnail((1280, 1280))
    frame = cv2.cvtColor(np.asarray(photo), cv2.COLOR_RGB2BGR)
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, found = detector.detect(frame)
    out = []
    if found is None:
        return out
    for face in sorted(found, key=lambda f: -float(f[14]))[:100]:
        x, y, w, h = [float(v) for v in face[:4]]
        if min(w, h) < 28:
            continue
        feature = recognizer.feature(recognizer.alignCrop(frame, face)).flatten().astype("float32")
        norm = float(np.linalg.norm(feature))
        if not np.isfinite(feature).all() or norm < 1e-8:
            continue
        feature /= norm
        pad = max(w, h) * .28
        crop = photo.crop((max(0, int(x-pad)), max(0, int(y-pad)), min(width, int(x+w+pad)), min(height, int(y+h+pad))))
        crop.thumbnail((320, 320))
        buffer = io.BytesIO()
        crop.save(buffer, "JPEG", quality=88)
        out.append((feature, buffer.getvalue(), float(face[14])))
    return out


def choose_person(feature, prototypes, ids, excluded=()):
    """Conservative first-prototype matching, with an ambiguity margin and no same-photo merges."""
    if not len(ids):
        return None
    scores = prototypes @ feature
    for i, pid in enumerate(ids):
        if pid in excluded:
            scores[i] = -1
    ranked = np.argsort(scores)[::-1]
    best = int(ranked[0])
    second = float(scores[ranked[1]]) if len(ranked) > 1 else -1
    return ids[best] if float(scores[best]) >= .55 and float(scores[best]) - second >= .08 else None


def index(task, owners=None, retry=False):
    scope.set_owners(owners)
    try:
        engine()  # Validate before doing any index writes.
        where, params = scope.where("f.owner", "f.cat='image'")
        rows = jobs.index_batch(task, "SELECT f.* FROM files f LEFT JOIN face_index i ON i.file_id=f.id" + where +
            " AND (i.file_id IS NULL OR i.path!=f.path OR i.mtime!=f.mtime OR i.size!=f.size" +
            (" OR i.state='error'" if retry else "") + ") ORDER BY f.ts DESC, f.id", params)
        count, errors = 0, 0
        task.progress(total=len(rows), done=0, stage="Finding people", message="Processing on this NAS")
        for n, (row, pending) in enumerate(_detect_ahead(rows)):
            task.progress(done=n, message=f"{n:,} of {len(rows):,} photos checked · {count:,} faces found")
            found, state = [], "done"
            try:
                if pending is None:
                    state = "unsupported"
                else:
                    found = pending.result()
            except Exception:
                state, errors = "error", errors + 1
            task.progress()  # Honor cancellation before committing this photo.
            with _lock, db.tx() as c:
                current = c.execute("SELECT path,mtime,size FROM files WHERE id=?", (row["id"],)).fetchone()
                if not current or tuple(current) != (row["path"], row["mtime"], row["size"]):
                    continue
                c.execute("DELETE FROM faces WHERE file_id=?", (row["id"],))
                bank = c.execute("SELECT id,prototype FROM people WHERE owner=?", (row["owner"],)).fetchall()
                ids = [r["id"] for r in bank]
                vectors = np.array([np.frombuffer(r["prototype"], dtype="float32") for r in bank], dtype="float32")
                used = set()
                for feature, crop, confidence in found:
                    person = choose_person(feature, vectors, ids, used)
                    if person is None:
                        person = c.execute("INSERT INTO people(owner,prototype,created) VALUES(?,?,?)",
                            (row["owner"], feature.tobytes(), time.time())).lastrowid
                    used.add(person)
                    c.execute("INSERT INTO faces(file_id,person_id,embedding,crop,score) VALUES(?,?,?,?,?)",
                        (row["id"], person, feature.tobytes(), crop, confidence))
                c.execute("INSERT OR REPLACE INTO face_index VALUES(?,?,?,?,?,?)",
                    (row["id"], row["path"], row["mtime"], row["size"], state, time.time()))
            count += len(found)
        task.progress(done=len(rows), stage="Ready", message=f"Found {count:,} faces · {errors:,} unreadable photos")
        return {"photos": len(rows), "faces": count, "errors": errors}
    finally:
        scope.set_owners(None)


def status():
    where, params = scope.where("f.owner", "f.cat='image'")
    row = db.conn().execute("SELECT COUNT(*) total, SUM(i.state='done') checked, SUM(i.state='error') errors, "
        "SUM(i.state='unsupported') unsupported FROM files f LEFT JOIN face_index i ON i.file_id=f.id "
        "AND i.path=f.path AND i.mtime=f.mtime AND i.size=f.size" + where, params).fetchone()
    return {**{k: row[k] or 0 for k in row.keys()}, "task": next((t for t in jobs.history()
        if t["kind"] == "faces" and t["status"] in ("queued", "running")), None),
        "local": True, "celebrity_available": os.getenv("CELEBRITY_MATCHING_ENABLED") == "1" and importlib.util.find_spec("boto3") is not None}


def listing(q="", offset=0, limit=120):
    where, params = scope.where("p.owner", "f.ignored=0 AND p.name LIKE ? ESCAPE '\\'",
        ["%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"])
    base = " FROM people p JOIN current_faces f ON f.person_id=p.id" + where
    total = db.conn().execute("SELECT COUNT(DISTINCT p.id)" + base, params).fetchone()[0]
    rows = db.conn().execute("SELECT p.id,p.name,p.owner,COUNT(DISTINCT f.file_id) photos,MIN(f.id) cover" + base +
        " GROUP BY p.id ORDER BY (p.name!='') DESC, photos DESC,p.id LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"items": [dict(r) for r in rows], "total": total}


def get_person(pid, c=None):
    where, params = scope.where(extra="id=?", params=[pid])
    row = (c or db.conn()).execute("SELECT id,name,owner FROM people" + where, params).fetchone()
    if not row:
        raise HTTPException(404, "Person not found in this library")
    return dict(row)


def face(fid):
    where, params = scope.where(extra="id=? AND ignored=0", params=[fid])
    row = db.conn().execute("SELECT * FROM current_faces" + where, params).fetchone()
    if not row:
        raise HTTPException(404, "Face is no longer available")
    return row


def detail(pid, offset=0, limit=120):
    person = get_person(pid)
    where, params = scope.where(extra="person_id=? AND ignored=0", params=[pid])
    rows = db.conn().execute("SELECT id,file_id,filename,ts FROM current_faces" + where +
        " ORDER BY ts DESC,id LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    count = db.conn().execute("SELECT COUNT(*) FROM current_faces" + where, params).fetchone()[0]
    return {**person, "faces": [dict(r) for r in rows], "total": count}


def rename(pid, name):
    name = str(name).strip()
    if len(name) > 80 or any(ord(c) < 32 for c in name):
        raise HTTPException(400, "Use a name of up to 80 characters")
    with _lock, db.tx() as c:
        get_person(pid, c)
        c.execute("UPDATE people SET name=? WHERE id=?", (name, pid))
    return {"ok": True}


def merge(source, target):
    if source == target:
        raise HTTPException(400, "Choose a different person")
    with _lock, db.tx() as c:
        a, b = get_person(source, c), get_person(target, c)
        if a["owner"] != b["owner"]:
            raise HTTPException(400, "People from different libraries stay separate")
        c.execute("UPDATE faces SET person_id=? WHERE person_id=?", (target, source))
        c.execute("DELETE FROM people WHERE id=?", (source,))
    return {"ok": True, "person_id": target}


def correct(fid, target=None, ignore=False):
    with _lock, db.tx() as c:
        row = face(fid)
        if ignore:
            c.execute("UPDATE faces SET ignored=1,person_id=NULL WHERE id=?", (fid,))
            return {"ok": True}
        if target:
            person = get_person(target, c)
            if person["owner"] != row["owner"]:
                raise HTTPException(400, "Choose a person in the same library")
        else:
            target = c.execute("INSERT INTO people(owner,prototype,created) VALUES(?,?,?)",
                (row["owner"], row["embedding"], time.time())).lastrowid
        c.execute("UPDATE faces SET person_id=? WHERE id=?", (target, fid))
    return {"ok": True, "person_id": target}


def clear():
    if jobs.intelligence.busy_with("faces"):
        raise HTTPException(409, "Pause face indexing before removing its data")
    with _lock, db.tx() as c:
        w, p = scope.where()
        c.execute("DELETE FROM faces WHERE person_id IN (SELECT id FROM people" + w + ")", p)
        fw, fp = scope.where()
        c.execute("DELETE FROM faces WHERE file_id IN (SELECT id FROM files" + fw + ")", fp)
        c.execute("DELETE FROM face_index WHERE file_id IN (SELECT id FROM files" + fw + ")", fp)
        c.execute("DELETE FROM people" + w, p)
        if not scope.owners():
            c.execute("DELETE FROM faces")
            c.execute("DELETE FROM face_index")
    return {"ok": True}
