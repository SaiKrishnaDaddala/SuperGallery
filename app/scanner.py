"""Walks the scan roots and keeps the `files` and `folders` tables in sync with disk."""
import logging
import os
import posixpath as pp
import time

from . import db, scope
from .config import EXCLUDE_NAMES, EXCLUDE_PREFIXES, EXT_CAT, SCAN_ROOTS

log = logging.getLogger("supergallery")

UPSERT = """
INSERT INTO files(path,dir,name,ext,cat,size,mtime,ts,seen,owner) VALUES(?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(path) DO UPDATE SET
  seen=excluded.seen, owner=excluded.owner,
  qhash=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.qhash END,
  hash=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.hash END,
  analyzed=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.analyzed ELSE 0 END,
  ts=CASE WHEN files.size=excluded.size AND files.mtime=excluded.mtime THEN files.ts ELSE excluded.ts END,
  cat=excluded.cat, size=excluded.size, mtime=excluded.mtime
"""


def excluded(name: str) -> bool:
    return name in EXCLUDE_NAMES or name.startswith(EXCLUDE_PREFIXES)


def split_ext(name: str) -> str:
    i = name.rfind(".")
    if i <= 0 or i == len(name) - 1:
        return ""
    ext = name[i + 1:].lower()
    return ext if len(ext) <= 12 else ""


def category(ext: str) -> str:
    return EXT_CAT.get(ext, "other")


def root_of(path: str) -> str | None:
    for r in SCAN_ROOTS:
        if path == r or path.startswith(r.rstrip("/") + "/"):
            return r
    return None


def scan(task):
    c = db.conn()
    gen = int(time.time() * 1000)
    folders: dict[str, list] = {}  # path -> [direct_size, direct_count, direct_dirs]
    batch: list[tuple] = []
    found = 0
    task.progress(0, 0, stage="Scanning folders")

    def flush():
        if batch:
            with db.tx() as t:
                t.executemany(UPSERT, batch)
            batch.clear()

    scanned_roots = []
    per_root: dict[str, int] = {}
    for root in SCAN_ROOTS:
        if not os.path.isdir(root):
            log.warning("scan root %s is missing or not mounted", root)
            continue
        scanned_roots.append(root)
        stack = [root]
        while stack:
            d = stack.pop()
            acc = folders.setdefault(d, [0, 0, 0])
            try:
                it = os.scandir(d)
            except OSError:
                continue
            with it:
                for e in it:
                    name = e.name
                    if excluded(name):
                        continue
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(pp.join(d, name))
                            acc[2] += 1
                            continue
                        if not e.is_file(follow_symlinks=False):
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    ext = split_ext(name)
                    fp = pp.join(d, name)
                    batch.append((fp, d, name, ext, category(ext), st.st_size, st.st_mtime, st.st_mtime, gen,
                                  scope.owner_of(fp)))
                    per_root[root] = per_root.get(root, 0) + 1
                    acc[0] += st.st_size
                    acc[1] += 1
                    found += 1
                    if len(batch) >= 5000:
                        flush()
                        task.progress(found, message=f"{found:,} files found")
        flush()
        task.progress(found, message=f"{found:,} files found")

    task.progress(stage="Removing deleted files from index")
    for root in scanned_roots:
        lo, hi = db.prefix_range(root)
        c.execute("DELETE FROM files WHERE seen<>? AND path>=? AND path<?", (gen, lo, hi))
    c.execute("DELETE FROM sim_groups WHERE file_id NOT IN (SELECT id FROM files)")

    task.progress(stage="Computing folder sizes")
    rebuild_folders(folders, scanned_roots)
    db.kv_set("last_scan", time.time())
    log.info("scan finished: %s files, %s folders; per root: %s", found, len(folders),
             ", ".join(f"{r}={n}" for r, n in per_root.items()) or "none")
    return {"files": found, "folders": len(folders)}


def rebuild_folders(folders: dict[str, list], roots: list[str]):
    total = {p: [v[0], v[1]] for p, v in folders.items()}
    rootset = set(roots)
    # Children have longer paths than their parents, so walking longest-first propagates sums upward.
    for p in sorted(folders, key=len, reverse=True):
        if p in rootset:
            continue
        parent = pp.dirname(p)
        if parent in total:
            total[parent][0] += total[p][0]
            total[parent][1] += total[p][1]
    rows = []
    for p, (size, count) in total.items():
        r = root_of(p)
        depth = 0 if p == r else p[len(r):].count("/")
        rows.append((p, None if p == r else pp.dirname(p), depth, size, count, folders[p][2]))
    with db.tx() as t:
        for r in roots:
            lo, hi = db.prefix_range(r)
            t.execute("DELETE FROM folders WHERE path=? OR (path>=? AND path<?)", (r, lo, hi))
        t.executemany("INSERT OR REPLACE INTO folders VALUES(?,?,?,?,?,?)", rows)


def ancestors(path: str):
    """Folders from the parent of `path` up to (and including) its scan root."""
    r = root_of(path)
    d = pp.dirname(path)
    while r and len(d) >= len(r):
        yield d
        if d == r:
            break
        d = pp.dirname(d)


def forget_files(rows: list[tuple[str, int]]):
    """Remove deleted/moved files from the index and subtract them from their folder totals."""
    adj: dict[str, list[int]] = {}
    for path, size in rows:
        for d in ancestors(path):
            a = adj.setdefault(d, [0, 0])
            a[0] += size
            a[1] += 1
    with db.tx() as t:
        t.executemany("DELETE FROM files WHERE path=?", [(p,) for p, _ in rows])
        t.executemany("UPDATE folders SET size=size-?, count=count-? WHERE path=?",
                      [(s, n, p) for p, (s, n) in adj.items()])


def forget_folder(path: str):
    lo, hi = db.prefix_range(path)
    c = db.conn()
    rows = c.execute("SELECT path,size FROM files WHERE path>=? AND path<?", (lo, hi)).fetchall()
    forget_files([(r[0], r[1]) for r in rows])
    with db.tx() as t:
        t.execute("DELETE FROM folders WHERE path=? OR (path>=? AND path<?)", (path, lo, hi))
        parent = pp.dirname(path)
        t.execute("UPDATE folders SET ndirs=MAX(ndirs-1,0) WHERE path=?", (parent,))


def index_file(path: str):
    """Add or refresh one file (after a move/restore/upload) without a full scan."""
    try:
        st = os.stat(path)
    except OSError:
        return
    name = pp.basename(path)
    ext = split_ext(name)
    db.conn().execute(UPSERT, (path, pp.dirname(path), name, ext, category(ext), st.st_size,
                               st.st_mtime, st.st_mtime, 0, scope.owner_of(path)))
    with db.tx() as t:
        ensure_folders(t, path)
        t.executemany("UPDATE folders SET size=size+?, count=count+1 WHERE path=?",
                      [(st.st_size, d) for d in ancestors(path)])


def ensure_folders(t, path: str):
    """Create index rows for folders made since the last scan (mkdir, upload, extract, organize)."""
    r = root_of(path)
    for d in ancestors(path):
        depth = 0 if d == r else d[len(r):].count("/")
        if t.execute("INSERT OR IGNORE INTO folders VALUES(?,?,?,0,0,0)",
                     (d, None if d == r else pp.dirname(d), depth)).rowcount and d != r:
            t.execute("UPDATE folders SET ndirs=ndirs+1 WHERE path=?", (pp.dirname(d),))


def move_folder(old: str, new: str):
    """Re-point the index after a folder was renamed/moved, keeping hashes and photo analysis."""
    c = db.conn()
    r = c.execute("SELECT size, count FROM folders WHERE path=?", (old,)).fetchone()
    size, count = (r[0], r[1]) if r else (0, 0)
    n = len(old) + 1
    lo, hi = db.prefix_range(old)
    with db.tx() as t:
        t.executemany("UPDATE folders SET size=size-?, count=count-? WHERE path=?",
                      [(size, count, d) for d in ancestors(old)])
        t.execute("UPDATE files SET path=?||substr(path,?), dir=?||substr(dir,?) WHERE path>=? AND path<?",
                  (new, n, new, n, lo, hi))
        t.execute("""UPDATE folders SET path=?||substr(path,?), parent=?||substr(parent,?)
                     WHERE path=? OR (path>=? AND path<?)""", (new, n, new, n, old, lo, hi))
        t.execute("UPDATE folders SET parent=? WHERE path=?", (pp.dirname(new), new))
        t.executemany("UPDATE folders SET size=size+?, count=count+? WHERE path=?",
                      [(size, count, d) for d in ancestors(new)])
