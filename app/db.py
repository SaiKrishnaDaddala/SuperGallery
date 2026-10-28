"""SQLite index. One connection per thread, WAL mode so the UI can read while indexing."""
import sqlite3
import threading
from contextlib import contextmanager

from .config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  dir TEXT NOT NULL,
  name TEXT NOT NULL,
  ext TEXT NOT NULL,
  cat TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime REAL NOT NULL,
  ts REAL NOT NULL,            -- photo taken time (EXIF) or mtime
  seen INTEGER NOT NULL,
  qhash TEXT,
  hash TEXT,
  analyzed INTEGER NOT NULL DEFAULT 0,  -- 0 pending, 1 ok, -1 not decodable
  width INTEGER, height INTEGER,
  ha INTEGER, hb INTEGER,      -- perceptual hashes (row / column dHash)
  blur REAL, bright REAL
);
CREATE INDEX IF NOT EXISTS ix_files_size ON files(size);
CREATE INDEX IF NOT EXISTS ix_files_hash ON files(hash);
CREATE INDEX IF NOT EXISTS ix_files_ext ON files(ext, size);
CREATE INDEX IF NOT EXISTS ix_files_cat_ts ON files(cat, ts);
CREATE INDEX IF NOT EXISTS ix_files_dir ON files(dir);
CREATE INDEX IF NOT EXISTS ix_files_mtime ON files(mtime);

CREATE TABLE IF NOT EXISTS folders(
  path TEXT PRIMARY KEY,
  parent TEXT,
  depth INTEGER NOT NULL,
  size INTEGER NOT NULL,
  count INTEGER NOT NULL,
  ndirs INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_folders_parent ON folders(parent);
CREATE INDEX IF NOT EXISTS ix_folders_size ON folders(size);

CREATE TABLE IF NOT EXISTS trash(
  id INTEGER PRIMARY KEY,
  orig_path TEXT NOT NULL,
  trash_path TEXT NOT NULL,
  size INTEGER NOT NULL,
  is_dir INTEGER NOT NULL DEFAULT 0,
  deleted_at REAL NOT NULL,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS sim_groups(
  gid INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  PRIMARY KEY(gid, file_id)
);
CREATE INDEX IF NOT EXISTS ix_sim_file ON sim_groups(file_id);

CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        # Every thread has its own connection: keep each private page cache small (8 MB) and read through
        # one shared memory map instead, which the OS can reclaim when other apps need memory.
        c.execute("PRAGMA cache_size=-8192")
        c.execute("PRAGMA mmap_size=268435456")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA busy_timeout=60000")
        _local.c = c
    return c


@contextmanager
def tx():
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        raise


MIGRATIONS = {
    "files": [("owner", "TEXT"), ("make", "TEXT"), ("sat", "REAL"), ("kind", "TEXT"), ("duration", "REAL")],
    "trash": [("owner", "TEXT"), ("cat", "TEXT"), ("kind", "TEXT")],
}

EXTRA = """
CREATE INDEX IF NOT EXISTS ix_files_owner ON files(owner, hash);
CREATE INDEX IF NOT EXISTS ix_files_kind ON files(kind, owner);
CREATE TABLE IF NOT EXISTS deletion_log(
  ts REAL NOT NULL, owner TEXT, cat TEXT, kind TEXT, ext TEXT, dir TEXT, size INTEGER, reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_dellog_kind ON deletion_log(kind);
"""


def init():
    from . import scope

    c = conn()
    c.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    c.executescript(EXTRA)
    c.create_function("owner_of", 1, scope.owner_of, deterministic=True)
    c.execute("UPDATE files SET owner=owner_of(path) WHERE owner IS NULL")
    # Photos analysed before categories existed get re-analysed once (adds camera make / colour / category).
    if kv_get("schema") != "2":
        c.execute("UPDATE files SET analyzed=0 WHERE cat='image' AND analyzed=1 AND kind IS NULL")
        kv_set("schema", "2")


def kv_get(k: str, default=None):
    r = conn().execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def kv_set(k: str, v):
    conn().execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))


def prefix_range(p: str) -> tuple[str, str]:
    """Bounds so that `path >= lo AND path < hi` matches everything under folder p (uses the path index)."""
    p = p.rstrip("/")
    return p + "/", p + "0"  # '0' is the character right after '/'
