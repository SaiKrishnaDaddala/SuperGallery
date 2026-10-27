"""Read-side queries: filters, analytics, duplicates, similar photos, smart cleanup, NL search."""
import re
import time

from . import db, scope, features
from .config import SCAN_ROOTS

YEAR = 365.25 * 86400
JUNK_NAMES = ("thumbs.db", ".ds_store", "desktop.ini", "ehthumbs.db", "ehthumbs_vista.db", ".localized",
              "zbthumbnail.info", ".picasa.ini", "picasa.ini", "albumart.jpg")
TEMP_EXT = ("tmp", "temp", "part", "crdownload", "partial", "download", "aria2", "!ut", "bc!", "opdownload")

# key -> (title, description, SQL condition, icon)
SMART = {
    "junk": ("System junk", "Thumbs.db, .DS_Store, desktop.ini, macOS ._ resource forks",
             f"(lower(name) IN ({','.join(repr(n) for n in JUNK_NAMES)}) OR name LIKE '.\\_%' ESCAPE '\\')", "broom"),
    "temp": ("Unfinished downloads & temp files", ".part, .crdownload, .tmp, Office ~$ lock files",
             f"(ext IN ({','.join(repr(e) for e in TEMP_EXT)}) OR name LIKE '~$%')", "hourglass"),
    "empty": ("Empty files", "Zero-byte files", "size=0", "file"),
    "logs": ("Log & crash dump files", ".log, .dmp, .old", "ext IN ('log','dmp','old')", "list"),
    "installers": ("Installers & disk images", ".exe, .msi, .apk, .dmg, .iso, .pkg",
                   "ext IN ('exe','msi','apk','dmg','iso','pkg','deb','rpm','appimage')", "package"),
    "blurry": ("Blurry photos", "Photos with very low sharpness",
               "cat='image' AND analyzed=1 AND blur<{blur} AND width*height>=250000", "blur"),
    "dark": ("Very dark photos", "Almost black photos (pocket shots, lens cap)",
             "cat='image' AND analyzed=1 AND bright<16", "moon"),
    "tiny": ("Tiny images", "Icons, thumbnails and web graphics under 200×200",
             "cat='image' AND analyzed=1 AND width*height<40000", "minimize"),
    "screenshots": ("Screenshots", "Screenshots and screen recordings",
                    "(lower(name) LIKE 'screenshot%' OR lower(name) LIKE 'screen shot%' OR lower(name) LIKE "
                    "'screen_shot%' OR lower(name) LIKE 'screenrecord%' OR lower(dir) LIKE '%/screenshots%')",
                    "monitor"),
    "old_large": ("Large files untouched for 2+ years", "Files over 500 MB not modified in 2 years",
                  "size>=524288000 AND mtime<{two_years_ago}", "archive"),
    "large_videos": ("Huge videos", "Videos over 2 GB", "cat='video' AND size>=2147483648", "film"),
}

SORTS = {"name": "name COLLATE NOCASE", "size": "size", "mtime": "mtime", "ts": "ts", "ext": "ext",
         "path": "path", "dir": "dir", "cat": "cat"}


def smart_sql(key: str, blur: float = 40) -> str:
    return SMART[key][2].format(blur=float(blur), two_years_ago=time.time() - 2 * YEAR)


def build_where(f: dict) -> tuple[str, list]:
    w, p = [], []
    f = f or {}
    if f.get("text"):
        from .search_index import text_condition
        clause, args = text_condition(f["text"])
        w.append(clause)
        p += args
    if f.get("owner"):
        w.append("owner=?")
        p.append(str(f["owner"]))
    if f.get("person_id"):
        features.require('people')
        w.append("id IN (SELECT file_id FROM current_faces WHERE person_id=? AND ignored=0)")
        p.append(int(f["person_id"]))
    if f.get("person_name"):
        features.require('people')
        w.append("id IN (SELECT cf.file_id FROM current_faces cf JOIN people p ON p.id=cf.person_id WHERE cf.ignored=0 AND lower(p.name)=lower(?))")
        p.append(str(f["person_name"]))
    if f.get("ids"):
        ids = [int(i) for i in f["ids"]]
        w.append(f"id IN ({','.join('?' * len(ids))})")
        p += ids
    if f.get("cat"):
        cats = [f["cat"]] if isinstance(f["cat"], str) else f["cat"]
        w.append(f"cat IN ({','.join('?' * len(cats))})")
        p += cats
    if f.get("ext"):
        exts = [f["ext"]] if isinstance(f["ext"], str) else f["ext"]
        exts = [e.lower().lstrip(".") for e in exts]
        w.append(f"ext IN ({','.join('?' * len(exts))})")
        p += exts
    if f.get("min_size") is not None:
        w.append("size>=?")
        p.append(int(f["min_size"]))
    if f.get("max_size") is not None:
        w.append("size<=?")
        p.append(int(f["max_size"]))
    if f.get("dir"):
        lo, hi = db.prefix_range(f["dir"])
        w.append("path>=? AND path<?")
        p += [lo, hi]
    if f.get("in_dir"):  # non-recursive
        w.append("dir=?")
        p.append(f["in_dir"].rstrip("/"))
    if f.get("q"):
        q = f["q"].strip()
        if "*" in q or "?" in q:
            w.append("lower(name) GLOB ?")
            p.append(q.lower())
        else:
            for word in q.lower().split():
                w.append("lower(name) LIKE ? ESCAPE '\\'")
                p.append("%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if f.get("path_q"):
        w.append("lower(path) LIKE ?")
        p.append("%" + f["path_q"].lower() + "%")
    if f.get("after") is not None:
        w.append("ts>=?")
        p.append(float(f["after"]))
    if f.get("before") is not None:
        w.append("ts<?")
        p.append(float(f["before"]))
    if f.get("mtime_before") is not None:
        w.append("mtime<?")
        p.append(float(f["mtime_before"]))
    if f.get("smart"):
        features.require('cleanup')
        w.append(smart_sql(f["smart"], f.get("blur", 40)))
    if f.get("dupes"):
        features.require('cleanup')
        w.append("hash IN (SELECT hash FROM files WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*)>1)")
    if f.get("min_pixels"):
        w.append("width*height>=?")
        p.append(int(f["min_pixels"]))
    if f.get("kind"):
        w.append(PHOTO_KINDS[f["kind"]][2])
    sc, sp = scope.cond()
    if sc:
        w.append(sc)
        p += sp
    return (" WHERE " + " AND ".join(w)) if w else "", p


ITEM_COLS = "id, path, dir, name, ext, cat, size, mtime, ts, width, height, hash, blur, owner, kind, duration"


def item(r) -> dict:
    return dict(r)


def query(f: dict, sort="size", order="desc", limit=200, offset=0) -> dict:
    c = db.conn()
    where, p = build_where(f)
    agg = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{where}", p).fetchone()
    col = SORTS.get(sort, "size")
    od = "ASC" if order == "asc" else "DESC"
    rows = c.execute(f"SELECT {ITEM_COLS} FROM files{where} ORDER BY {col} {od}, id LIMIT ? OFFSET ?",
                     p + [int(limit), int(offset)]).fetchall()
    return {"total": agg[0], "total_size": agg[1], "items": [item(r) for r in rows]}


def ids_for(f: dict, cap=2_000_000) -> list[int]:
    where, p = build_where(f)
    return [r[0] for r in db.conn().execute(f"SELECT id FROM files{where} LIMIT ?", p + [cap])]


# ---------------------------------------------------------------- analytics

_stats_cache: dict = {}


def invalidate():
    _stats_cache.clear()


def _cached(key: str, fn, ttl=120):
    key = f"{key}|{scope.key()}"
    hit = _stats_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _stats_cache[key] = (time.time(), val)
    return val


def stats() -> dict:
    return _cached("stats", _stats)


def _stats() -> dict:
    c = db.conn()
    W, P = scope.where()
    tot = c.execute("SELECT COUNT(*), COALESCE(SUM(size),0), COALESCE(AVG(size),0), COALESCE(MAX(size),0) "
                    f"FROM files{W}", P).fetchone()
    by_cat = [dict(r) for r in c.execute(
        f"SELECT cat, COUNT(*) count, SUM(size) size, AVG(size) avg FROM files{W} GROUP BY cat ORDER BY size DESC", P)]
    by_ext = [dict(r) for r in c.execute(
        f"SELECT ext, MAX(cat) cat, COUNT(*) count, SUM(size) size, AVG(size) avg, MAX(size) max FROM files{W} "
        "GROUP BY ext ORDER BY size DESC LIMIT 40", P)]
    edges = [0, 100 << 10, 1 << 20, 10 << 20, 100 << 20, 1 << 30, 10 << 30]
    labels = ["<100K", "100K–1M", "1–10M", "10–100M", "100M–1G", "1–10G", ">10G"]
    case = " ".join(f"WHEN size<{edges[i + 1]} THEN {i}" for i in range(len(edges) - 1))
    hist = {r[0]: (r[1], r[2]) for r in c.execute(
        f"SELECT CASE {case} ELSE {len(edges) - 1} END b, COUNT(*), SUM(size) FROM files{W} GROUP BY b", P)}
    size_hist = [{"label": labels[i], "count": hist.get(i, (0, 0))[0], "size": hist.get(i, (0, 0))[1] or 0}
                 for i in range(len(labels))]
    by_year = [dict(r) for r in c.execute(
        "SELECT CAST(strftime('%Y', ts, 'unixepoch') AS INTEGER) year, COUNT(*) count, SUM(size) size "
        f"FROM files{W} GROUP BY year ORDER BY year", P)]
    largest = [item(r) for r in c.execute(f"SELECT {ITEM_COLS} FROM files{W} ORDER BY size DESC LIMIT 25", P)]
    bases = scope.bases()
    if scope.owners():
        # Top level = folders directly inside each selected home / shared root.
        ph = ",".join("?" * len(bases))
        fc, fp = scope.folder_cond("path")
        top_rows = c.execute(f"SELECT path, size, count FROM folders WHERE parent IN ({ph}) "
                             "ORDER BY size DESC LIMIT 60", bases).fetchall()
        tf_rows = c.execute(f"SELECT path, size, count, depth FROM folders WHERE {fc} AND path NOT IN ({ph}) "
                            "ORDER BY size DESC LIMIT 25", fp + bases).fetchall()
    else:
        top_rows = c.execute("SELECT path, size, count FROM folders WHERE depth=1 ORDER BY size DESC LIMIT 60").fetchall()
        tf_rows = c.execute("SELECT path, size, count, depth FROM folders WHERE depth BETWEEN 1 AND 4 "
                            "ORDER BY size DESC LIMIT 25").fetchall()
    dup = duplicates({}, limit=0, per_user=True)
    PW, PP = scope.where(extra="cat='image' AND analyzed=0")
    pending = c.execute(f"SELECT COUNT(*) FROM files{PW}", PP).fetchone()[0]
    return {
        "total_files": tot[0], "total_size": tot[1], "avg_size": tot[2], "max_size": tot[3],
        "by_cat": by_cat, "by_ext": by_ext, "size_hist": size_hist, "by_year": by_year,
        "largest": largest, "top_level": [dict(r) for r in top_rows], "top_folders": [dict(r) for r in tf_rows],
        "dupes": {"groups": dup["groups"], "extra_files": dup["extra_files"], "wasted": dup["wasted"]},
        "photos_pending": pending, "roots": SCAN_ROOTS, "last_scan": float(db.kv_get("last_scan", 0) or 0),
        "scope": list(scope.owners() or []),
    }


def extensions(dir: str | None = None) -> list[dict]:
    where, p = build_where({"dir": dir} if dir else {})
    return [dict(r) for r in db.conn().execute(
        "SELECT ext, MAX(cat) cat, COUNT(*) count, SUM(size) size, AVG(size) avg, MAX(size) max, "
        f"MIN(mtime) oldest, MAX(mtime) newest FROM files{where} GROUP BY ext ORDER BY size DESC", p)]


def timeline(f: dict) -> list[dict]:
    where, p = build_where(f)
    return [dict(r) for r in db.conn().execute(
        f"SELECT strftime('%Y-%m', ts, 'unixepoch') month, COUNT(*) count, SUM(size) size FROM files{where} "
        "GROUP BY month ORDER BY month DESC", p)]


def folder_children(path: str) -> list[dict]:
    return [dict(r) for r in db.conn().execute(
        "SELECT path, size, count, ndirs FROM folders WHERE parent=? ORDER BY size DESC", (path.rstrip("/"),))]


def empty_folders(limit=5000) -> list[dict]:
    fc, fp = scope.folder_cond("path")
    homes = set(scope.bases())
    sql = "SELECT path FROM folders WHERE count=0 AND depth>=1" + (f" AND {fc}" if fc else "") + " ORDER BY path"
    rows = db.conn().execute(sql, fp).fetchall()
    # Only report the top-most empty folder of each empty subtree (never a user's home itself).
    out, last = [], None
    for (p,) in rows:
        if p in homes or (last and p.startswith(last + "/")):
            continue
        out.append({"path": p})
        last = p
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- duplicates

def _dup_filter(f: dict) -> tuple[str, list]:
    w, p = ["hash IS NOT NULL"], []
    sc, sp = scope.cond()
    if sc:
        w.append(sc)
        p += sp
    if f.get("cat"):
        w.append("cat=?")
        p.append(f["cat"])
    if f.get("min_size"):
        w.append("size>=?")
        p.append(int(f["min_size"]))
    if f.get("ext"):
        w.append("ext=?")
        p.append(f["ext"])
    if f.get("dir"):
        lo, hi = db.prefix_range(f["dir"])
        w.append("hash IN (SELECT hash FROM files WHERE path>=? AND path<? AND hash IS NOT NULL)")
        p += [lo, hi]
    return " AND ".join(w), p


def duplicates(f: dict, limit=50, offset=0, sort="wasted", per_user=True) -> dict:
    """per_user=True: copies only count as duplicates when the same user has them more than once (safe default).
    per_user=False: copies across all selected users are grouped together."""
    c = db.conn()
    w, p = _dup_filter(f)
    gb = "owner, hash" if per_user else "hash"
    order = {"wasted": "wasted DESC", "count": "n DESC, wasted DESC", "size": "size DESC"}.get(sort, "wasted DESC")
    summary = c.execute(f"""SELECT COUNT(*), COALESCE(SUM(n-1),0), COALESCE(SUM(wasted),0) FROM
        (SELECT COUNT(*) n, MAX(size)*(COUNT(*)-1) wasted FROM files WHERE {w} GROUP BY {gb} HAVING n>1)""",
                        p).fetchone()
    out = []
    if limit:
        groups = c.execute(f"""SELECT hash, MAX(owner) owner, MAX(size) size, COUNT(*) n, MAX(size)*(COUNT(*)-1) wasted
            FROM files WHERE {w} GROUP BY {gb} HAVING n>1 ORDER BY {order} LIMIT ? OFFSET ?""",
                           p + [limit, offset]).fetchall()
        sc, sp = scope.cond()
        for g in groups:
            if per_user:
                mw, mp = "hash=? AND owner=?", [g["hash"], g["owner"]]
            else:
                mw, mp = ("hash=? AND " + sc, [g["hash"]] + sp) if sc else ("hash=?", [g["hash"]])
            files = [item(r) for r in c.execute(f"SELECT {ITEM_COLS} FROM files WHERE {mw} ORDER BY mtime", mp)]
            recommended = _pick_keeper(files,'recommended',None)
            out.append({"hash": g["hash"], "owner": g["owner"] if per_user else None, "size": g["size"],
                        "count": g["n"], "wasted": g["wasted"], "files": files,
                        "recommended_id":recommended['id'], "recommendation":"Identical contents. Keeps the copy outside backup, download and chat folders, preferring camera and photo folders, then the older copy."})
    return {"groups": summary[0], "extra_files": summary[1], "wasted": summary[2], "items": out,
            "per_user": per_user}


_JUNK_WORDS = {"trashed", "cache", "thumbnail"}
_COPY_WORDS = {"backup", "whatsapp", "telegram", "download", "received", "sent", "export", "copy", "duplicate", "temp", "tmp"}
_ORIGINAL_WORDS = {"dcim", "camera", "original", "photo", "picture"}


def _folder_words(path: str) -> set:
    """Words in the folders below the library root: 'MobileBackup/Phone backups' -> {mobile, backup, phone}."""
    for root in SCAN_ROOTS:
        if path.startswith(root.rstrip("/") + "/"):
            path = path[len(root.rstrip("/")) + 1:]
            break
    words = set()
    for folder in path.split("/")[:-1]:
        for token in re.findall(r"[A-Za-z0-9]+", folder):
            # Keep the whole word ('WhatsApp') and its camel-case parts ('MobileBackup' -> mobile, backup).
            for w in {token, *re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", token)}:
                w = w.lower()
                words.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return words


def _recommended_rank(x: dict) -> tuple:
    """Lower is better: not junk, not a backup/forwarded/downloaded copy, from a camera/photos folder,
    no 'copy'/'(1)' suffix, then the older and shorter path."""
    words = _folder_words(x["path"])
    return (bool(words & _JUNK_WORDS), bool(words & _COPY_WORDS), not (words & _ORIGINAL_WORDS),
            bool(re.search(r"(?i)(?:copy|\(\d+\))", x["name"])), x["mtime"], len(x["path"]), x["id"])


def _pick_keeper(files: list, keep: str, prefer_dir: str | None):
    pool = files
    if prefer_dir:
        pd = prefer_dir.rstrip("/") + "/"
        pref = [x for x in files if x["path"].startswith(pd)]
        pool = pref or files
    keyf = {
        "recommended": _recommended_rank,
        "oldest": lambda x: (x["mtime"], len(x["path"])),
        "newest": lambda x: (-x["mtime"], len(x["path"])),
        "shortest_path": lambda x: (len(x["path"]), x["path"]),
        "longest_path": lambda x: (-len(x["path"]), x["path"]),
        "shortest_name": lambda x: (len(x["name"]), x["path"]),
        "largest": lambda x: (-(x.get("width") or 0) * (x.get("height") or 0), -x["size"], x["mtime"]),
        "smallest": lambda x: ((x.get("width") or 0) * (x.get("height") or 0), x["size"]),
        "sharpest": lambda x: (-(x.get("blur") or 0), -x["size"]),
    }.get(keep, lambda x: (x["mtime"], len(x["path"])))
    return min(pool, key=keyf)


def duplicates_autoselect(f: dict, keep="oldest", prefer_dir=None, only_in_dir=None, per_user=True) -> dict:
    """Mark every copy except one keeper per group. `only_in_dir`: only mark copies inside that folder."""
    c = db.conn()
    w, p = _dup_filter(f)
    rows = c.execute(f"SELECT id, hash, owner, path, name, mtime, size FROM files WHERE {w} ORDER BY hash", p).fetchall()
    sel, total, groups = [], 0, {}
    for r in rows:
        groups.setdefault((r["owner"], r["hash"]) if per_user else r["hash"], []).append(dict(r))
    groups = {k: v for k, v in groups.items() if len(v) > 1}
    od = only_in_dir.rstrip("/") + "/" if only_in_dir else None
    for files in groups.values():
        keeper = _pick_keeper(files, keep, prefer_dir)
        if od and keeper["path"].startswith(od):
            outside = [x for x in files if not x["path"].startswith(od)]
            if outside:
                keeper = outside[0]
        for x in files:
            if x["id"] != keeper["id"] and (not od or x["path"].startswith(od)):
                sel.append([x["id"], x["size"]])
                total += x["size"]
    return {"items": sel, "size": total, "groups": len(groups)}


# ---------------------------------------------------------------- similar photos

SIM_COLS = ("g.gid, f.id, f.path, f.dir, f.name, f.ext, f.cat, f.size, f.mtime, f.ts, f.width, f.height, "
            "f.hash, f.blur, f.owner, f.kind")


def _sim_groups(per_user: bool) -> list[list[dict]]:
    def build():
        sc, sp = scope.cond("f.owner")
        rows = db.conn().execute(f"SELECT {SIM_COLS} FROM sim_groups g JOIN files f ON f.id=g.file_id"
                                 + (f" WHERE {sc}" if sc else ""), sp).fetchall()
        groups: dict = {}
        for r in rows:
            groups.setdefault((r["gid"], r["owner"]) if per_user else r["gid"], []).append(dict(r))
        out = []
        for files in groups.values():
            if len(files) > 1:
                files.sort(key=lambda x: (-(x["width"] or 0) * (x["height"] or 0), -x["size"]))
                out.append(files)
        out.sort(key=lambda fs: -sum(x["size"] for x in fs[1:]))
        return out
    return _cached(f"sim:{per_user}", build, ttl=60)


def similar(limit=40, offset=0, per_user=True) -> dict:
    groups = _sim_groups(per_user)
    items = [{"gid": offset + i, "owner": g[0]["owner"] if per_user else None, "files": g,
              "reclaim": sum(x["size"] for x in g[1:])} for i, g in enumerate(groups[offset:offset + limit])]
    return {"groups": len(groups), "photos": sum(len(g) for g in groups),
            "reclaim": sum(sum(x["size"] for x in g[1:]) for g in groups), "items": items, "per_user": per_user,
            "threshold": int(db.kv_get("similar_threshold", 10)),
            "computed_at": float(db.kv_get("similar_at", 0) or 0)}


def similar_autoselect(keep="largest", per_user=True) -> dict:
    sel, total = [], 0
    groups = _sim_groups(per_user)
    for files in groups:
        keeper = _pick_keeper(files, keep, None)
        for x in files:
            if x["id"] != keeper["id"]:
                sel.append([x["id"], x["size"]])
                total += x["size"]
    return {"items": sel, "size": total, "groups": len(groups)}


# ---------------------------------------------------------------- photo & video categories

# key -> (title, description, SQL condition, icon)
PHOTO_KINDS = {
    "camera": ("Camera photos", "Real photos from a phone or camera", "kind='camera'", "image"),
    "chat": ("WhatsApp & chat images", "Memes, forwards and photos received in WhatsApp, Telegram, Instagram…",
             "kind='chat'", "sparkles"),
    "web": ("Downloaded & saved images", "Small images saved from the web or apps (no camera info)", "kind='web'",
            "download"),
    "screenshot": ("Screenshots", "Phone and computer screenshots", "kind='screenshot'", "monitor"),
    "document": ("Documents & receipts", "Photos of paper, receipts, notes and whiteboards", "kind='document'",
                 "fileText"),
    "lowq": ("Low quality", "Low resolution or heavily compressed photos", "kind='lowq'", "minimize"),
    "blurry": ("Blurry", "Out of focus or shaky shots", "kind='blurry'", "blur"),
    "dark": ("Too dark", "Pocket shots and almost black photos", "kind='dark'", "moon"),
    "tiny": ("Icons & thumbnails", "Images smaller than 200×200", "kind='tiny'", "grid"),
    "cache": ("Phone thumbnail cache",
              "Android .thumbnails and app caches inside phone backups. The phone rebuilds them, so they are safe to delete",
              "(kind='cache' OR (cat<>'image' AND (lower(path) LIKE '%/.thumbnails/%' OR lower(name) LIKE '.thumbdata%')))",
              "broom"),
    "phonetrash": ("Phone recycle-bin leftovers",
                   "Files already deleted on the phone (.trashed-…, .Trash) that are still in the backup",
                   "(kind='phonetrash' OR (cat<>'image' AND (lower(name) LIKE '.trashed-%' OR lower(path) LIKE '%/.trash/%')))",
                   "trash"),
    "other": ("Other images", "Edited, downloaded or unclassified images", "kind='other'", "images"),
    "screenrec": ("Screen recordings", "Videos recorded from a screen",
                  "cat='video' AND (lower(name) LIKE 'screenrecord%' OR lower(name) LIKE 'screen recording%' OR "
                  "lower(name) LIKE 'screen_recording%' OR lower(name) LIKE 'rpreplay%' OR "
                  "lower(name) LIKE 'record_20%')", "video"),
    "msgvideo": ("Messaging videos", "WhatsApp, Telegram and other forwarded videos",
                 "cat='video' AND (lower(name) LIKE 'vid-%-wa%' OR lower(path) LIKE '%whatsapp%' OR "
                 "lower(path) LIKE '%telegram%' OR lower(path) LIKE '%instagram%')", "film"),
    "shortclip": ("Short clips", "Videos under 5 seconds — accidental recordings and live-photo leftovers",
                  "cat='video' AND duration IS NOT NULL AND duration<5", "play"),
    "uhd": ("4K videos", "Ultra-HD videos — the biggest space users", "cat='video' AND width*height>=7000000", "film"),
    "longvideo": ("Long videos", "Videos longer than 20 minutes", "cat='video' AND duration>=1200", "film"),
    "camvideo": ("Camera videos", "Videos recorded on your phone or camera",
                 "cat='video' AND lower(path) NOT LIKE '%whatsapp%' AND (lower(name) LIKE 'vid!_%' ESCAPE '!' OR "
                 "lower(name) LIKE 'mov!_%' ESCAPE '!' OR lower(name) LIKE 'pxl!_%' ESCAPE '!' OR "
                 "lower(name) LIKE 'img!_%' ESCAPE '!' OR lower(name) LIKE 'dji!_%' ESCAPE '!' OR "
                 "lower(name) LIKE 'gopr%' OR lower(name) LIKE 'dsc%' OR lower(name) LIKE '20%')", "film"),
}
VIDEO_KINDS = {"screenrec", "msgvideo", "camvideo", "shortclip", "uhd", "longvideo"}


def categories() -> dict:
    def build():
        c = db.conn()
        out = []
        for key, (title, desc, cond, icon) in PHOTO_KINDS.items():
            W, P = scope.where(extra=cond)
            n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
            sample = [r[0] for r in c.execute(f"SELECT id FROM files{W} ORDER BY ts DESC LIMIT 6", P)]
            out.append({"key": key, "title": title, "desc": desc, "icon": icon, "count": n, "size": s,
                        "sample": sample, "video": key in VIDEO_KINDS})
        PW, PP = scope.where(extra="cat='image' AND analyzed=0")
        pending = c.execute(f"SELECT COUNT(*) FROM files{PW}", PP).fetchone()[0]
        return {"categories": out, "pending": pending}
    return _cached("categories", build)


# ---------------------------------------------------------------- smart cleanup & insights

def cleanup_summary(blur=40) -> list[dict]:
    return _cached(f"cleanup:{blur}", lambda: _cleanup_summary(blur))


def _cleanup_summary(blur) -> list[dict]:
    c = db.conn()
    out = []
    for key, (title, desc, _sql, icon) in SMART.items():
        W, P = scope.where(extra=smart_sql(key, blur))
        n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
        out.append({"key": key, "title": title, "desc": desc, "icon": icon, "count": n, "size": s})
    return out


KIND_PLURAL = {"chat": "WhatsApp & chat images", "web": "downloaded images", "cache": "phone cache thumbnails",
               "phonetrash": "phone recycle-bin leftovers", "screenshot": "screenshots", "document": "document photos",
               "lowq": "low-quality photos", "blurry": "blurry photos", "dark": "dark photos", "tiny": "tiny images",
               "camera": "camera photos", "other": "images", "screenrec": "screen recordings",
               "msgvideo": "messaging videos", "camvideo": "camera videos"}


def learned() -> list[dict]:
    """Recommendations learned from what was deleted before (photo category, folder and file-type patterns)."""
    def build():
        c = db.conn()
        sc, sp = scope.cond()
        lw = f" AND {sc}" if sc else ""
        recs = []
        for kind, n_del in c.execute(f"SELECT kind, COUNT(*) FROM deletion_log WHERE kind IS NOT NULL{lw} "
                                     "GROUP BY kind HAVING COUNT(*)>=5 ORDER BY 2 DESC", sp).fetchall():
            if kind not in PHOTO_KINDS or kind == "camera":
                continue
            W, P = scope.where(extra=PHOTO_KINDS[kind][2])
            n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
            if n:
                label = KIND_PLURAL.get(kind, kind)
                recs.append({"kind": "learned", "icon": PHOTO_KINDS[kind][3], "size": s, "count": n,
                             "title": f"{n:,} more {label}", "view": f"#/categories/{kind}",
                             "text": f"You deleted {n_del:,} {label} before. These look just like them."})
        for d, cat, n_del in c.execute(f"SELECT dir, cat, COUNT(*) FROM deletion_log WHERE dir IS NOT NULL{lw} "
                                       "GROUP BY dir, cat HAVING COUNT(*)>=5 ORDER BY 3 DESC LIMIT 10", sp).fetchall():
            W, P = scope.where(extra="dir=? AND cat=?", params=[d, cat])
            n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
            if n:
                recs.append({"kind": "learned", "icon": "folder", "size": s, "count": n,
                             "title": f"{n:,} {cat} files left in {d.rsplit('/', 1)[-1]}",
                             "view": f"#/search?dir={d}&cat={cat}",
                             "text": f"You already removed {n_del:,} {cat} files from this folder."})
        for ext, n_del in c.execute(f"SELECT ext, COUNT(*) FROM deletion_log WHERE ext<>''{lw} "
                                    "GROUP BY ext HAVING COUNT(*)>=10 ORDER BY 2 DESC LIMIT 5", sp).fetchall():
            W, P = scope.where(extra="ext=?", params=[ext])
            n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
            if n:
                recs.append({"kind": "learned", "icon": "file", "size": s, "count": n,
                             "title": f"{n:,} more .{ext} files", "view": f"#/search?ext={ext}&sort=size",
                             "text": f"You deleted {n_del:,} .{ext} files before."})
        recs.sort(key=lambda r: -r["size"])
        return recs[:8]
    return _cached("learned", build)


def insights() -> list[dict]:
    return _cached("insights", _insights)


def _insights() -> list[dict]:
    st = stats()
    tips = []
    d = st["dupes"]
    if d["extra_files"]:
        tips.append({"kind": "dupes", "title": f"{d['extra_files']:,} duplicate copies",
                     "size": d["wasted"], "view": "#/duplicates",
                     "text": f"{d['groups']:,} files exist more than once for the same user. "
                             "One click keeps one copy of each."})
    sim = similar(limit=0)
    if sim["groups"]:
        tips.append({"kind": "similar", "title": f"{sim['groups']:,} groups of look-alike photos",
                     "size": sim["reclaim"], "view": "#/similar",
                     "text": "Resized copies, re-saves and burst shots. Keep the best, remove the rest."})
    for cat in categories()["categories"]:
        if cat["count"] and cat["key"] in ("cache", "phonetrash", "chat", "web", "screenshot", "lowq", "blurry",
                                           "dark", "screenrec"):
            tips.append({"kind": cat["key"], "title": f"{cat['count']:,} {KIND_PLURAL.get(cat['key'], cat['title'])}",
                         "size": cat["size"], "view": f"#/categories/{cat['key']}", "text": cat["desc"]})
    for cat in cleanup_summary():
        if cat["count"] and cat["key"] in ("junk", "temp", "empty", "old_large", "installers"):
            tips.append({"kind": cat["key"], "title": f"{cat['count']:,} {cat['title'].lower()}",
                         "size": cat["size"], "view": f"#/cleanup/{cat['key']}", "text": cat["desc"]})
    ef = len(empty_folders(limit=100000))
    if ef:
        tips.append({"kind": "empty_folders", "title": f"{ef:,} empty folders", "size": 0,
                     "view": "#/cleanup/empty_folders", "text": "Folders with no files inside (including sub-folders)."})
    if st["total_size"] and st["by_cat"]:
        top = st["by_cat"][0]
        label = {"image": "Photos", "video": "Videos", "audio": "Music", "document": "Documents",
                 "archive": "Archives", "app": "Installers", "code": "Code"}.get(top["cat"], "Other files")
        tips.append({"kind": "info", "title": f"{label} use {100 * top['size'] / st['total_size']:.0f}% of the space",
                     "size": top["size"], "view": f"#/search?cat={top['cat']}&sort=size",
                     "text": f"{top['count']:,} {top['cat']} files. Review the biggest ones first."})
    tips.sort(key=lambda t: -t["size"])
    return tips


# ---------------------------------------------------------------- natural-language search

UNITS = {"b": 1, "kb": 1 << 10, "k": 1 << 10, "mb": 1 << 20, "m": 1 << 20, "gb": 1 << 30, "g": 1 << 30, "tb": 1 << 40}
CAT_WORDS = {
    "image": r"photos?|images?|pictures?|pics?|jpe?gs?",
    "video": r"videos?|movies?|films?|clips?",
    "audio": r"music|songs?|audio|mp3s?|tracks?",
    "document": r"documents?|docs?|papers?|spreadsheets?",
    "archive": r"archives?|zips?|compressed",
    "app": r"installers?|programs?|apps?",
    "code": r"code|source|scripts?",
}
SMART_WORDS = {"blurry": "blurry", "blurred": "blurry", "dark": "dark", "screenshots?": "screenshots",
               "junk": "junk", "temp(orary)?": "temp", "empty": "empty", "tiny": "tiny", "logs?": "logs"}


def parse_nl(text: str) -> dict:
    """'videos bigger than 2gb from 2019 in Movies' -> filter + sort. Rule based, no cloud needed."""
    s = " " + text.lower().strip() + " "
    f: dict = {}
    sort, order, view = None, "desc", None
    now = time.time()

    def size_of(num, unit):
        return int(float(num) * UNITS.get(unit or "mb", 1 << 20))

    m = re.search(r"(?:larger|bigger|greater|more|over|above|>=?|at least)\s*(?:than\s*)?([\d.]+)\s*(tb|gb|mb|kb|g|m|k|b)?\b", s)
    if m:
        f["min_size"] = size_of(m.group(1), m.group(2))
        s = s.replace(m.group(0), " ")
    m = re.search(r"(?:smaller|less|under|below|<=?|at most)\s*(?:than\s*)?([\d.]+)\s*(tb|gb|mb|kb|g|m|k|b)?\b", s)
    if m:
        f["max_size"] = size_of(m.group(1), m.group(2))
        s = s.replace(m.group(0), " ")
    m = re.search(r"\b(?:between)\s*(\d{4})\s*(?:and|-|to)\s*(\d{4})\b", s)
    if m:
        f["after"] = time.mktime((int(m.group(1)), 1, 1, 0, 0, 0, 0, 0, -1))
        f["before"] = time.mktime((int(m.group(2)) + 1, 1, 1, 0, 0, 0, 0, 0, -1))
        s = s.replace(m.group(0), " ")
    m = re.search(r"\bbefore\s+(\d{4})\b", s)
    if m:
        f["before"] = time.mktime((int(m.group(1)), 1, 1, 0, 0, 0, 0, 0, -1))
        s = s.replace(m.group(0), " ")
    m = re.search(r"\b(?:after|since)\s+(\d{4})\b", s)
    if m:
        f["after"] = time.mktime((int(m.group(1)) + (0 if "since" in m.group(0) else 1), 1, 1, 0, 0, 0, 0, 0, -1))
        s = s.replace(m.group(0), " ")
    m = re.search(r"\b(?:in|from|of|taken in)?\s*((?:19|20)\d{2})\b", s)
    if m and "after" not in f and "before" not in f:
        y = int(m.group(1))
        f["after"] = time.mktime((y, 1, 1, 0, 0, 0, 0, 0, -1))
        f["before"] = time.mktime((y + 1, 1, 1, 0, 0, 0, 0, 0, -1))
        s = s.replace(m.group(0), " ")
    m = re.search(r"\bolder than\s+(\d+)\s*(years?|months?|days?)\b", s)
    if m:
        mult = {"y": YEAR, "m": YEAR / 12, "d": 86400}[m.group(2)[0]]
        f["mtime_before"] = now - int(m.group(1)) * mult
        s = s.replace(m.group(0), " ")
    for word, rng in (("today", 86400), ("this week", 7 * 86400), ("last week", 7 * 86400),
                      ("this month", 31 * 86400), ("last month", 31 * 86400), ("this year", YEAR), ("last year", YEAR)):
        if f" {word} " in s or f"{word} " in s.lstrip():
            f["after"] = now - (2 * rng if word.startswith("last") else rng)
            s = s.replace(word, " ")
            break
    m = re.search(r"\b(?:in|inside|under)\s+(?:folder\s+|the\s+)?\"?([\w .\-/]+?)\"?\s+(?:folder\s+)?(?=$|\s)", s)
    if m:
        name = m.group(1).strip().strip("/")
        r = db.conn().execute("SELECT path FROM folders WHERE lower(path) LIKE ? ORDER BY depth, size DESC LIMIT 1",
                              ("%/" + name,)).fetchone()
        if r:
            f["dir"] = r[0]
            s = s.replace(m.group(0), " ")
    m = re.search(r"\b(?:named|called|containing|with name)\s+\"?([^\"]+?)\"?\s*$", s.strip() + " ")
    if m:
        f["q"] = m.group(1).strip()
        s = s.replace(m.group(0), " ")
    m = re.search(r"\"([^\"]+)\"", s)
    if m:
        f["q"] = m.group(1)
        s = s.replace(m.group(0), " ")
    exts = re.findall(r"(?:^|\s)\.?([a-z0-9]{2,5})(?=\s)", s)
    from .config import EXT_CAT

    found_ext = [e for e in exts if e in EXT_CAT and e not in ("doc", "docs", "code", "key", "pages")]
    cats = [c for c, rx in CAT_WORDS.items() if re.search(rf"\b(?:{rx})\b", s)]
    if found_ext and not (len(found_ext) == 1 and found_ext[0] in ("jpg", "jpeg") and "image" in cats):
        f["ext"] = found_ext
    elif cats:
        f["cat"] = cats
    for rx, key in SMART_WORDS.items():
        if re.search(rf"\b{rx}\b", s):
            f["smart"] = key
            break
    if re.search(r"\bduplicates?|dupes?|copies\b", s):
        view = "duplicates"
    if re.search(r"\bsimilar|look ?alike\b", s):
        view = "similar"
    if re.search(r"\b(largest|biggest|huge|heaviest)\b", s):
        sort = "size"
    elif re.search(r"\b(smallest|tiny)\b", s):
        sort, order = "size", "asc"
    elif re.search(r"\b(oldest|earliest)\b", s):
        sort, order = "ts", "asc"
    elif re.search(r"\b(newest|latest|recent)\b", s):
        sort = "ts"
    return {"filter": f, "sort": sort or "size", "order": order, "view": view}


# ---------------------------------------------------------------- users overview

def users_overview() -> list[dict]:
    """Per-user storage, photo/video split and how much each user could reclaim."""
    def build():
        prev = scope.owners()
        out = []
        try:
            for u in scope.list_users():
                if not u["count"]:
                    continue
                scope.set_owners([u["name"]])
                c = db.conn()
                W, P = scope.where()
                cats = {r[0]: (r[1], r[2] or 0) for r in c.execute(
                    f"SELECT cat, COUNT(*), SUM(size) FROM files{W} GROUP BY cat", P)}
                kinds = {}
                for k in ("chat", "screenshot", "phonetrash", "cache", "camera"):
                    KW, KP = scope.where(extra=PHOTO_KINDS[k][2])
                    kinds[k] = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{KW}", KP).fetchone()
                d = duplicates({}, limit=0, per_user=True)
                sim = similar(limit=0, per_user=True)
                reclaim = d["wasted"] + kinds["phonetrash"][1] + kinds["cache"][1]
                out.append({
                    **u,
                    "photos": cats.get("image", (0, 0)), "videos": cats.get("video", (0, 0)),
                    "docs": cats.get("document", (0, 0)), "other": sum(v[1] for k, v in cats.items()
                                                                      if k not in ("image", "video", "document")),
                    "kinds": {k: list(v) for k, v in kinds.items()},
                    "dupes": {"extra": d["extra_files"], "wasted": d["wasted"]},
                    "similar": {"groups": sim["groups"], "reclaim": sim["reclaim"]},
                    "safe_reclaim": reclaim,
                })
        finally:
            scope.set_owners(list(prev) if prev else None)
        out.sort(key=lambda r: -r["size"])
        return out
    return _cached("users_overview", build, ttl=180)


# ---------------------------------------------------------------- quick clean

QUICK = [
    ("phonetrash", "Phone recycle-bin leftovers", "Files already deleted on the phone, still in the backup",
     {"kind": "phonetrash"}, "trash"),
    ("cache", "Phone thumbnail cache", "Thumbnails the phone rebuilds by itself", {"kind": "cache"}, "broom"),
    ("dupes", "Duplicate copies", "Extra copies inside the same user (the oldest copy is kept)", None, "copy"),
    ("junk", "System junk", "Thumbs.db, .DS_Store, desktop.ini, ._ files", {"smart": "junk"}, "broom"),
    ("temp", "Unfinished downloads & temp files", ".part, .crdownload, .tmp", {"smart": "temp"}, "hourglass"),
    ("empty", "Empty files", "Zero-byte files", {"smart": "empty"}, "file"),
]


def quickclean_summary() -> list[dict]:
    def build():
        c = db.conn()
        out = []
        for key, title, desc, flt, icon in QUICK:
            if flt is None:
                d = duplicates({}, limit=0, per_user=True)
                n, s = d["extra_files"], d["wasted"]
            else:
                W, P = build_where(flt)
                n, s = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM files{W}", P).fetchone()
            out.append({"key": key, "title": title, "desc": desc, "icon": icon, "count": n, "size": s})
        return out
    return _cached("quickclean", build, ttl=60)


def quickclean_ids(keys: list[str]) -> list[int]:
    ids: set[int] = set()
    for key, _t, _d, flt, _i in QUICK:
        if key not in keys:
            continue
        if flt is None:
            ids.update(i for i, _s in duplicates_autoselect({}, keep="oldest", per_user=True)["items"])
        else:
            ids.update(ids_for(flt))
    return sorted(ids)


# ---------------------------------------------------------------- duplicate folders

def duplicate_folders(per_user=True) -> list[dict]:
    """Folders whose files are byte-identical to another folder's files (e.g. a backup copied twice)."""
    def build():
        import hashlib

        sc, sp = scope.cond()
        rows = db.conn().execute("SELECT dir, owner, hash, size FROM files WHERE size>0"
                                 + (f" AND {sc}" if sc else ""), sp)
        folders: dict[str, list] = {}
        for d, owner, h, size in rows:
            f = folders.setdefault(d, [owner, [], 0, False])
            if h is None:
                f[3] = True  # a unique file: this folder can't be a full copy of another one
            else:
                f[1].append(h)
                f[2] += size
        groups: dict = {}
        for d, (owner, hashes, size, has_unique) in folders.items():
            if has_unique or len(hashes) < 2:
                continue
            sig = hashlib.blake2b("".join(sorted(hashes)).encode(), digest_size=12).hexdigest()
            groups.setdefault((owner, sig) if per_user else sig, []).append({"path": d, "size": size,
                                                                             "count": len(hashes), "owner": owner})
        out = []
        for members in groups.values():
            if len(members) < 2:
                continue
            # skip nested copies (a folder and its own sub-folder) — keep only top-most distinct ones
            members.sort(key=lambda m: (len(m["path"]), m["path"]))
            out.append({"folders": members, "size": members[0]["size"], "count": members[0]["count"],
                        "reclaim": members[0]["size"] * (len(members) - 1)})
        out.sort(key=lambda g: -g["reclaim"])
        return out
    return _cached(f"dupfolders:{per_user}", build, ttl=120)
