"""Exact-duplicate detection: size -> quick hash (head/middle/tail) -> full content hash.

Only files that share a size are ever read, and only files that also share a quick hash are
read completely, so a multi-terabyte NAS is hashed with a small fraction of the I/O.
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor

from . import db
from .config import HASH_WORKERS, MIN_DUP_SIZE

CHUNK = 65536
FULL_READ = 1 << 20


def quick_hash(path: str, size: int) -> str | None:
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            if size <= 3 * CHUNK:
                h.update(f.read())
            else:
                h.update(f.read(CHUNK))
                f.seek(size // 2)
                h.update(f.read(CHUNK))
                f.seek(size - CHUNK)
                h.update(f.read(CHUNK))
    except OSError:
        return None
    return h.hexdigest()


def full_hash(path: str) -> str | None:
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            while chunk := f.read(FULL_READ):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _run(task, rows, fn, sql, pack, stage):
    total = sum(r[2] for r in rows)
    task.progress(0, total, stage=stage, message=f"{len(rows):,} files")
    out = []
    done = 0
    with ThreadPoolExecutor(HASH_WORKERS) as pool:
        for i in range(0, len(rows), 1000):  # chunked so a cancel takes effect quickly
            part = rows[i:i + 1000]
            for (fid, _path, size), value in zip(part, pool.map(fn, part)):
                done += size
                if value is not None:
                    out.append(pack(fid, size, value))
            with db.tx() as t:
                t.executemany(sql, out)
            out.clear()
            task.progress(done)
    if out:
        with db.tx() as t:
            t.executemany(sql, out)
    task.progress(done)


def hash_duplicates(task):
    c = db.conn()
    rows = c.execute(
        """SELECT f.id, f.path, f.size FROM files f
           JOIN (SELECT size FROM files WHERE size>=? GROUP BY size HAVING COUNT(*)>1) s ON f.size=s.size
           WHERE f.qhash IS NULL""", (MIN_DUP_SIZE,)).fetchall()
    # Small files are fully covered by the quick hash, so it doubles as their content hash.
    _run(task, rows, lambda r: quick_hash(r[1], r[2]),
         "UPDATE files SET qhash=?, hash=COALESCE(?, hash) WHERE id=?",
         lambda fid, size, v: (v, v if size <= 3 * CHUNK else None, fid), "Quick-hashing same-size files")

    rows = c.execute(
        """SELECT f.id, f.path, f.size FROM files f
           JOIN (SELECT size, qhash FROM files WHERE qhash IS NOT NULL AND size>? GROUP BY size, qhash
                 HAVING COUNT(*)>1) g ON f.size=g.size AND f.qhash=g.qhash
           WHERE f.hash IS NULL""", (3 * CHUNK,)).fetchall()
    _run(task, rows, lambda r: full_hash(r[1]), "UPDATE files SET hash=? WHERE id=?",
         lambda fid, size, v: (v, fid), "Verifying duplicates (full content hash)")
    return {"hashed": len(rows)}
