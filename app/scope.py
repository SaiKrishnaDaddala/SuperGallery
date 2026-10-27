"""Which NAS users the current request is about.

Every file has an `owner`: the user whose personal folder it lives in (first folder under USERS_ROOT),
or "shared" for everything in shared folders. The UI sends the selected users in the X-SG-Users header;
the middleware stores them here and every query narrows itself with `where()`.
"""
import contextvars

from . import db
from .config import SCAN_ROOTS, USERS_ROOT

SHARED = "shared"
_current: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar("sg_scope", default=None)


def set_owners(owners: list[str] | None):
    _current.set(tuple(sorted(set(owners))) if owners else None)


def owners() -> tuple[str, ...] | None:
    return _current.get()


def key() -> str:
    o = owners()
    return ",".join(o) if o else "*"


def owner_of(path: str) -> str:
    if USERS_ROOT and path.startswith(USERS_ROOT + "/"):
        rel = path[len(USERS_ROOT) + 1:]
        if "/" in rel:  # a loose file directly in the homes folder belongs to nobody
            return rel.split("/", 1)[0]
    return SHARED


def cond(col: str = "owner") -> tuple[str, list]:
    """SQL condition (without WHERE) limiting rows to the selected owners, or ("", [])."""
    o = owners()
    if not o:
        return "", []
    return f"{col} IN ({','.join('?' * len(o))})", list(o)


def where(col: str = "owner", extra: str = "", params: list | None = None) -> tuple[str, list]:
    """' WHERE <scope> AND <extra>' helper."""
    c, p = cond(col)
    parts = [x for x in (c, extra) if x]
    return (" WHERE " + " AND ".join(parts)) if parts else "", p + (params or [])


def bases() -> list[str]:
    """Folder paths that make up the current scope (user homes and/or shared roots)."""
    o = owners()
    shared_roots = [r for r in SCAN_ROOTS if r != USERS_ROOT]
    if not o:
        return list(SCAN_ROOTS)
    out = []
    for name in o:
        if name == SHARED:
            out += shared_roots
        elif USERS_ROOT:
            out.append(f"{USERS_ROOT}/{name}")
    return out


def folder_cond(col: str = "path") -> tuple[str, list]:
    """Condition on a folder/file path column restricting it to the scope's base folders."""
    if not owners():
        return "", []
    parts, params = [], []
    for b in bases():
        lo, hi = db.prefix_range(b)
        parts.append(f"({col}=? OR ({col}>=? AND {col}<?))")
        params += [b, lo, hi]
    return ("(" + " OR ".join(parts) + ")") if parts else "0", params


def list_users() -> list[dict]:
    """Owners with their totals, plus homes that exist on disk but hold no files yet."""
    import os

    c = db.conn()
    rows = {r[0]: {"name": r[0], "count": r[1], "size": r[2] or 0}
            for r in c.execute("SELECT owner, COUNT(*), SUM(size) FROM files GROUP BY owner")}
    if USERS_ROOT and os.path.isdir(USERS_ROOT):
        for e in os.scandir(USERS_ROOT):
            if e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "@", "#")):
                rows.setdefault(e.name, {"name": e.name, "count": 0, "size": 0})
    users = sorted((r for k, r in rows.items() if k and k != SHARED), key=lambda r: r["name"].lower())
    for u in users:
        u["kind"] = "user"
    shared = rows.get(SHARED, {"name": SHARED, "count": 0, "size": 0})
    shared["kind"] = "shared"
    return users + [shared]
