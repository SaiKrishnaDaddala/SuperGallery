"""SuperGallery — HTTP API + static web UI."""
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import posixpath as pp
import secrets
import shutil
import threading
import time
import zipfile

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from urllib.parse import unquote

from . import analyzer, db, features, fileops, hasher, jobs, queries, rules, scanner, scope, similar, thumbs, video
from .config import (APP_PASSWORD, CONFIG_DIR, DECODABLE, SCAN_INTERVAL_HOURS, SCAN_ROOTS, TRASH_NAME,
                     TRASH_RETENTION_DAYS, VIDEO_THUMB, WEB_DIR, fwd)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("supergallery")

app = FastAPI(title="SuperGallery", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")

from .auth_http import install as install_auth
install_auth(app)


class TextCompression:
    """Gzip the page, scripts, styles and JSON; never photos, videos, downloads or ranged reads."""
    MEDIA_PATHS = ("/api/raw", "/api/thumb", "/api/zip", "/api/trash/thumb", "/api/faces/", "/api/visual/frame",
                   "/api/backups/")
    MEDIA_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif", "image/avif", "video/mp4", "audio/mpeg",
                   "application/zip", "application/pdf", "application/octet-stream")

    def __init__(self, app):
        from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=1024, compresslevel=6,
                                   exclude_content_types=DEFAULT_EXCLUDED_CONTENT_TYPES + self.MEDIA_TYPES)

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and not scope["path"].startswith(self.MEDIA_PATHS)
                and not any(name == b"range" for name, _ in scope["headers"])):
            return await self.gzip(scope, receive, send)
        return await self.app(scope, receive, send)


app.add_middleware(TextCompression)
from .intelligence_http import router as intelligence_router
app.include_router(intelligence_router)
from .discovery_http import router as discovery_router
app.include_router(discovery_router)
from .safety_http import router as safety_router
app.include_router(safety_router)
from .uploads_http import router as uploads_router
app.include_router(uploads_router)
app.include_router(features.router)
from .network import router as network_router
app.include_router(network_router)


# ---------------------------------------------------------------- helpers

def err(e: Exception):
    raise HTTPException(400, str(e))


def submit_op(label, fn, *a, reindex=False, **kw):
    t = jobs.ops.submit(jobs.Task("op", label, _invalidating(fn, reindex), *a, **kw))
    return {"task": t.id}


def _invalidating(fn, reindex=False):
    def run(task, *a, **kw):
        try:
            return fn(task, *a, **kw)
        finally:
            queries.invalidate()
            if reindex:  # new paths need hashes / photo analysis; cheap because only new rows are processed
                start_index("Index new files", rescan=False)
    return run


def full_index(task, rescan=True):
    t0 = time.time()
    if rescan:
        scanner.scan(task)
    queries.invalidate()
    h = hasher.hash_duplicates(task) if features.enabled('cleanup') else {'skipped': True}
    log.info("duplicate hashing finished: %s", h)
    queries.invalidate()
    analyzer.analyze_images(task)
    video.analyze_videos(task)
    sim = similar.compute(task, int(db.kv_get("similar_threshold", similar.DEFAULT_THRESHOLD))) if features.enabled('cleanup') else {'skipped': True}
    log.info("similar photos: %s", sim)
    queries.invalidate()
    c = db.conn()
    per_owner = ", ".join(f"{r[0]}={r[1]} files/{(r[2] or 0) / 2**30:.1f} GB" for r in
                          c.execute("SELECT owner, COUNT(*), SUM(size) FROM files GROUP BY owner"))
    log.info("index ready in %.0fs - %s", time.time() - t0, per_owner or "no files")
    from . import intelligence_tasks
    intelligence_tasks.refresh_enabled()
    task.progress(stage="Done", message="Index is up to date")
    return {"ok": True}


def start_index(label="Full scan", rescan=True):
    from . import backups
    if backups.pending():return None
    if jobs.indexer.busy_with("index"):
        return None
    return jobs.indexer.submit(jobs.Task("index", label, full_index, rescan=rescan))


def scheduler():
    time.sleep(5)
    if not db.kv_get("last_scan"):
        start_index("First-time scan")
    elif db.conn().execute("SELECT 1 FROM files WHERE cat IN ('image','video') AND analyzed=0 LIMIT 1").fetchone():
        start_index("Analyze new photos & videos", rescan=False)
    last_purge = 0.0
    while True:
        from . import backups
        if backups.pending():
            time.sleep(5)
            continue
        last = float(db.kv_get("last_scan", 0) or 0)
        if SCAN_INTERVAL_HOURS > 0 and time.time() - last > SCAN_INTERVAL_HOURS * 3600:
            start_index("Scheduled rescan")
        try:
            rules.due()
        except Exception:  # noqa: BLE001 - a broken rule must not stop the scheduler
            log.exception("auto-cleanup rules failed")
        if time.time() - last_purge > 6 * 3600:
            last_purge = time.time()
            jobs.ops.submit(jobs.Task("purge", f"Purge recycle bin (> {TRASH_RETENTION_DAYS} days)", fileops.purge_old_trash))
        time.sleep(60)


@app.on_event("startup")
def startup():
    from . import backups
    backups.apply_pending()
    from .upgrade import backup
    backup(CONFIG_DIR, '2.4')
    db.init()
    from . import people, search_index
    people.init()
    search_index.init()
    from . import visual_search, albums, intelligence_tasks
    visual_search.init(); albums.init(); intelligence_tasks.init()
    analyzer.reclassify_all()
    jobs.start()
    from . import memory
    memory.start()
    intelligence_tasks.resume()
    threading.Thread(target=scheduler, daemon=True, name="scheduler").start()
    log.info("SuperGallery ready. Roots: %s", SCAN_ROOTS)


# ---------------------------------------------------------------- status & tasks

@app.get("/api/status")
def status():
    c = db.conn()
    n = c.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files").fetchone()
    tr = c.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM trash").fetchone()
    return {"tasks": jobs.history(), "files": n[0], "size": n[1], "trash_count": tr[0], "trash_size": tr[1],
            "last_scan": float(db.kv_get("last_scan", 0) or 0), "roots": SCAN_ROOTS,
            "ffmpeg": bool(thumbs.VIDEO), "auth": True, "env_password": bool(APP_PASSWORD),
            "scan_interval_hours": SCAN_INTERVAL_HOURS, "trash_days": TRASH_RETENTION_DAYS,
            "version": features.VERSION, "features": features.settings()}


@app.post("/api/scan")
def scan(body: dict = Body(default={})):
    if body.get("mode") == "similar":
        features.require('cleanup')
        t = jobs.indexer.submit(jobs.Task("similar", "Regroup similar photos", _invalidating(similar.compute),
                                          int(body.get("threshold", similar.DEFAULT_THRESHOLD))))
        return {"task": t.id}
    t = start_index("Manual scan")
    return {"task": t.id if t else None, "already_running": t is None}


@app.post("/api/tasks/{task_id}/cancel")
def cancel(task_id: int):
    t = jobs.get(task_id)
    if t:
        t.cancel_requested = True
        from . import intelligence_tasks
        intelligence_tasks.cancel(t)
    return {"ok": bool(t)}


@app.get("/api/tasks/{task_id}")
def task_info(task_id: int):
    t = jobs.get(task_id)
    if not t:
        raise HTTPException(404)
    return t.to_dict()


# ---------------------------------------------------------------- analytics

@app.get("/api/stats")
def stats():
    return queries.stats()


@app.get("/api/insights")
def insights():
    return queries.insights() if features.enabled('cleanup') else []


@app.get("/api/extensions")
def extensions(dir: str | None = None):
    return queries.extensions(dir)


@app.get("/api/folders")
def folders(path: str):
    return queries.folder_children(path)


@app.post("/api/query")
def query(body: dict = Body(...)):
    return queries.query(body.get("filter") or {}, body.get("sort", "size"), body.get("order", "desc"),
                         min(int(body.get("limit", 200)), 5000), int(body.get("offset", 0)))


@app.post("/api/query/ids")
def query_ids(body: dict = Body(...)):
    ids = queries.ids_for(body.get("filter") or {})
    return {"ids": ids}


@app.post("/api/timeline")
def timeline(body: dict = Body(default={})):
    return queries.timeline(body.get("filter") or {})


@app.post("/api/nlq")
def nlq(body: dict = Body(...)):
    return queries.parse_nl(body.get("q", ""))


@app.get("/api/users")
def users():
    return scope.list_users()


@app.get("/api/users/overview")
def users_overview():
    return queries.users_overview()


@app.get("/api/quickclean")
def quickclean():
    return queries.quickclean_summary()


@app.post("/api/quickclean/run")
def quickclean_run(body: dict = Body(...)):
    keys = [k for k in body.get("keys") or [] if isinstance(k, str)]
    ids = queries.quickclean_ids(keys)
    if not ids:
        err(ValueError("nothing to clean"))
    return submit_op(f"Quick clean: {len(ids):,} items", fileops.delete, ids=ids, permanent=False, guard="dupes",
                     reason="quick clean")


@app.get("/api/dupfolders")
def dupfolders(per_user: bool = True):
    return queries.duplicate_folders(per_user)


@app.post("/api/dupfolders/delete")
def dupfolders_delete(body: dict = Body(...)):
    paths = set(body.get("paths") or [])
    groups = queries.duplicate_folders(bool(body.get("per_user", True)))
    allowed = set()
    for g in groups:
        members = {m["path"] for m in g["folders"]}
        chosen = members & paths
        if chosen and chosen != members:  # always keep at least one copy of every folder
            allowed |= chosen
    if not allowed:
        err(ValueError("select at least one copy to remove and keep one copy of each folder"))
    return submit_op(f"Remove {len(allowed):,} duplicate folders", fileops.delete, paths=sorted(allowed),
                     permanent=False, reason="duplicate folders")


@app.get("/api/rules")
def rules_list():
    out = rules.load()
    for r in out:
        r["preview"] = rules.preview(r)
    return {"rules": out, "templates": rules.TEMPLATES}


@app.put("/api/rules")
def rules_save(body: dict = Body(...)):
    return {"rules": rules.save(body.get("rules") or [])}


@app.post("/api/rules/preview")
def rules_preview(body: dict = Body(...)):
    return rules.preview({"target": body.get("target") or {}, "older_days": int(body.get("older_days") or 0),
                          "users": body.get("users")})


@app.post("/api/rules/{rule_id}/run")
def rules_run(rule_id: str):
    t = jobs.ops.submit(jobs.Task("rule", "Auto-cleanup (manual run)", _invalidating(rules.run), rule_id))
    return {"task": t.id}


@app.get("/api/categories")
def categories():
    return queries.categories()


@app.get("/api/learned")
def learned():
    return queries.learned()


@app.post("/api/duplicates")
def duplicates(body: dict = Body(default={})):
    return queries.duplicates(body.get("filter") or {}, int(body.get("limit", 50)), int(body.get("offset", 0)),
                              body.get("sort", "wasted"), bool(body.get("per_user", True)))


@app.post("/api/duplicates/autoselect")
def dup_autoselect(body: dict = Body(default={})):
    return queries.duplicates_autoselect(body.get("filter") or {}, body.get("keep", "oldest"),
                                         body.get("prefer_dir") or None, body.get("only_in_dir") or None,
                                         bool(body.get("per_user", True)))


@app.post("/api/similar")
def similar_groups(body: dict = Body(default={})):
    return queries.similar(int(body.get("limit", 40)), int(body.get("offset", 0)), bool(body.get("per_user", True)))


@app.post("/api/similar/autoselect")
def similar_autoselect(body: dict = Body(default={})):
    return queries.similar_autoselect(body.get("keep", "largest"), bool(body.get("per_user", True)))


@app.get("/api/cleanup")
def cleanup(blur: float = 40):
    return {"categories": queries.cleanup_summary(blur), "empty_folders": len(queries.empty_folders(100000))}


@app.get("/api/empty-folders")
def empty_folders():
    return queries.empty_folders()


# ---------------------------------------------------------------- file manager

def _entry(e: os.DirEntry, parent: str, ids: dict, fol: dict):
    try:
        is_dir = e.is_dir(follow_symlinks=False)
        st = e.stat(follow_symlinks=False)
    except OSError:
        return None
    ext = "" if is_dir else scanner.split_ext(e.name)
    path = pp.join(parent, e.name)
    d = {"name": e.name, "path": path, "dir": is_dir, "mtime": st.st_mtime,
         "ext": ext, "cat": "folder" if is_dir else scanner.category(ext), "hidden": e.name.startswith(".")}
    if is_dir:
        f = fol.get(path)
        d["size"], d["count"] = (f[0], f[1]) if f else (None, None)
    else:
        d["size"] = st.st_size
        meta = ids.get(path)
        if meta:
            d["id"], d["w"], d["h"] = meta
    return d


@app.get("/api/browse")
def browse(path: str = ""):
    if not path:
        c = db.conn()
        out = []
        for r in SCAN_ROOTS:
            f = c.execute("SELECT size, count FROM folders WHERE path=?", (r,)).fetchone()
            try:
                du = shutil.disk_usage(r)
                disk = {"total": du.total, "used": du.used, "free": du.free}
            except OSError:
                disk = None
            out.append({"name": pp.basename(r) or r, "path": r, "dir": True, "cat": "volume", "ext": "",
                        "mtime": 0, "size": f[0] if f else None, "count": f[1] if f else None, "disk": disk})
        return {"path": "", "parent": None, "entries": out, "root": True}
    try:
        rp = fileops.safe_path(path, allow_root=True)
    except fileops.OpError as e:
        err(e)
    if not os.path.isdir(rp):
        raise HTTPException(404, "folder not found")
    c = db.conn()
    ids = {r[0]: (r[1], r[2], r[3]) for r in c.execute("SELECT path, id, width, height FROM files WHERE dir=?", (rp,))}
    fol = {r[0]: (r[1], r[2]) for r in c.execute("SELECT path, size, count FROM folders WHERE parent=?", (rp,))}
    entries = []
    with os.scandir(rp) as it:
        for e in it:
            if e.name == TRASH_NAME or scanner.excluded(e.name):
                continue
            d = _entry(e, rp, ids, fol)
            if d:
                entries.append(d)
    root = scanner.root_of(rp)
    try:
        du = shutil.disk_usage(rp)
        disk = {"total": du.total, "used": du.used, "free": du.free}
    except OSError:
        disk = None
    return {"path": rp, "parent": None if rp == root else pp.dirname(rp), "root_path": root, "entries": entries,
            "disk": disk}


@app.get("/api/info")
def info(path: str, hash: bool = False):
    try:
        rp = fileops.safe_path(path, allow_root=True)
    except fileops.OpError as e:
        err(e)
    try:
        st = os.lstat(rp)
    except FileNotFoundError:
        raise HTTPException(404, "This file no longer exists.")
    c = db.conn()
    out = {"path": rp, "name": pp.basename(rp), "size": st.st_size, "mtime": st.st_mtime, "ctime": st.st_ctime,
           "mode": oct(st.st_mode & 0o777), "uid": st.st_uid, "gid": st.st_gid, "dir": os.path.isdir(rp),
           "mime": mimetypes.guess_type(rp)[0]}
    if out["dir"]:
        f = c.execute("SELECT size, count, ndirs FROM folders WHERE path=?", (rp,)).fetchone()
        if f:
            out.update(size=f[0], count=f[1], ndirs=f[2])
        return out
    r = c.execute("SELECT id, hash, width, height, ts, blur, bright FROM files WHERE path=?", (rp,)).fetchone()
    if r:
        out.update(id=r[0], hash=r[1], width=r[2], height=r[3], taken=r[4], sharpness=r[5], brightness=r[6])
        if r[1]:
            out["copies"] = [x[0] for x in c.execute("SELECT path FROM files WHERE hash=? AND id<>?", (r[1], r[0]))]
    if hash and not out.get("hash"):
        out["hash"] = hasher.full_hash(rp)
    return out


def _path_for(file_id: int | None, path: str | None) -> str:
    if file_id is not None:
        r = db.conn().execute("SELECT path FROM files WHERE id=?", (file_id,)).fetchone()
        if not r:
            raise HTTPException(404)
        path = r[0]
    try:
        return fileops.safe_path(path or "", allow_root=True)
    except fileops.OpError as e:
        err(e)


@app.get("/api/thumb")
def thumb(path: str | None = None, id: int | None = None, s: int = 256):
    rp = _path_for(id, path)
    s = 256 if s <= 256 else 512 if s <= 512 else 1600 if s <= 1600 else 2560
    out = thumbs.render(rp, scanner.split_ext(pp.basename(rp)), s)
    if not out:
        raise HTTPException(415, "no preview")
    return FileResponse(out, media_type="image/webp", headers={"Cache-Control": "private, max-age=604800"})


@app.get("/api/raw")
def raw(path: str | None = None, id: int | None = None, download: bool = False):
    rp = _path_for(id, path)
    if not os.path.isfile(rp):
        raise HTTPException(404)
    mt = mimetypes.guess_type(rp)[0] or "application/octet-stream"
    inline_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif", "application/pdf"}
    download = download or not (mt in inline_types or mt.startswith(("video/", "audio/")))
    return FileResponse(rp, media_type=mt, filename=pp.basename(rp),
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Content-Security-Policy": "sandbox; default-src 'none'; frame-ancestors 'self'"})


@app.get("/api/text")
def text(path: str, limit: int = 262144):
    rp = _path_for(None, path)
    try:
        with open(rp, "rb") as f:
            data = f.read(max(0, min(limit, 2 << 20)))
    except FileNotFoundError:
        raise HTTPException(404, "This file no longer exists.")
    return Response(data.decode("utf-8", "replace"), media_type="text/plain; charset=utf-8")


class _Pipe:
    """Write-only, non-seekable buffer, so zipfile streams with data descriptors."""

    def __init__(self):
        self.buf = bytearray()

    def write(self, b):
        self.buf += b
        return len(b)

    def flush(self):
        pass

    def take(self):
        b = bytes(self.buf)
        self.buf.clear()
        return b


@app.get("/api/zip")
def zip_download(paths: str, name: str = "download"):
    srcs = [_path_for(None, p) for p in json.loads(paths)]

    def gen():
        pipe = _Pipe()
        with zipfile.ZipFile(pipe, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for s in srcs:
                base = pp.dirname(s)
                walk = os.walk(s) if os.path.isdir(s) else [(base, [], [pp.basename(s)])]
                for dp, _ds, fs in walk:
                    dp = fwd(dp)
                    _ds[:] = [d for d in _ds if not os.path.islink(pp.join(dp, d)) and d not in scanner.EXCLUDE_NAMES and not d.startswith(scanner.EXCLUDE_PREFIXES)]
                    for fn in fs:
                        fp = pp.join(dp, fn)
                        try:
                            if os.path.islink(fp):
                                continue
                            fp = fileops.safe_path(fp)
                            with open(fp, "rb") as src, z.open(fp[len(base) + 1:], "w", force_zip64=True) as dst:
                                while chunk := src.read(1 << 20):
                                    dst.write(chunk)
                                    yield pipe.take()
                        except (OSError, fileops.OpError):
                            continue
                        yield pipe.take()
        yield pipe.take()

    return StreamingResponse(gen(), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


@app.post("/api/upload")
async def upload(dir: str = Form(...), files: list[UploadFile] = File(...), relpaths: str = Form("[]")):
    dest = _path_for(None, dir)
    rels = json.loads(relpaths or "[]")
    saved = []
    for i, uf in enumerate(files):
        rel = (rels[i] if i < len(rels) and rels[i] else uf.filename or "upload").replace("\\", "/")
        rel = "/".join(x for x in rel.split("/") if x not in ("", ".", ".."))
        target = fileops.unique_dest(pp.join(dest, rel))
        try:
            fileops.safe_path(target)
        except fileops.OpError as e:
            err(e)
        os.makedirs(pp.dirname(target), exist_ok=True)
        with open(target, "wb") as out:
            while chunk := await uf.read(1 << 20):
                out.write(chunk)
        scanner.index_file(target)
        saved.append(target)
    queries.invalidate()
    start_index("Index uploaded files", rescan=False)
    return {"saved": saved}


@app.post("/api/mkdir")
def mkdir(body: dict = Body(...)):
    try:
        return {"path": fileops.mkdir(body["parent"], body["name"].strip())}
    except (OSError, fileops.OpError) as e:
        err(e)


@app.post("/api/rename")
def rename(body: dict = Body(...)):
    try:
        p = fileops.rename(body["path"], body["name"].strip())
        queries.invalidate()
        return {"path": p}
    except (OSError, fileops.OpError) as e:
        err(e)


@app.post("/api/rename/preview")
def rename_preview(body: dict = Body(...)):
    try:
        plan = fileops.rename_plan(body["paths"], body.get("find", ""), body.get("replace", ""),
                                   body.get("mode", "text"), int(body.get("start", 1)), body.get("case"))
    except Exception as e:  # noqa: BLE001 - bad regex etc.
        err(e)
    names = [n for _, n in plan]
    clashes = {n for n in names if names.count(n) > 1}
    return {"items": [{"path": p, "old": pp.basename(p), "new": n, "clash": n in clashes} for p, n in plan]}


@app.post("/api/rename/bulk")
def rename_bulk(body: dict = Body(...)):
    plan = [(x["path"], x["new"]) for x in body["items"]]
    return submit_op(f"Rename {len(plan):,} items", fileops.bulk_rename, plan)


def _targets(body: dict):
    ids = body.get("ids") or []
    if body.get("filter"):
        ids = queries.ids_for(body["filter"])
    return ids, body.get("paths") or []


@app.post("/api/delete")
def delete(body: dict = Body(...)):
    ids, paths = _targets(body)
    n = len(ids) + len(paths)
    if not n:
        err(ValueError("nothing selected"))
    permanent = bool(body.get("permanent"))
    label = f"{'Delete' if permanent else 'Recycle'} {n:,} item{'s' if n != 1 else ''}"
    return submit_op(label, fileops.delete, ids=ids, paths=paths, permanent=permanent,
                     guard=body.get("guard"), reason=body.get("reason"))


@app.post("/api/move")
def move(body: dict = Body(...)):
    ids, paths = _targets(body)
    copy = bool(body.get("copy"))
    n = len(ids) + len(paths)
    return submit_op(f"{'Copy' if copy else 'Move'} {n:,} items → {pp.basename(body['dest'])}",
                     fileops.move, body["dest"], ids=ids, paths=paths, copy=copy, reindex=True)


@app.post("/api/compress")
def compress(body: dict = Body(...)):
    return submit_op(f"Compress {len(body['paths'])} items", fileops.compress, body["paths"], body["dest"],
                     body.get("name") or "archive", reindex=True)


@app.post("/api/extract")
def extract(body: dict = Body(...)):
    return submit_op(f"Extract {pp.basename(body['path'])}", fileops.extract, body["path"], body.get("dest"), reindex=True)


@app.post("/api/empty-folders/delete")
def empty_folders_delete(body: dict = Body(...)):
    return submit_op(f"Remove {len(body['paths']):,} empty folders", fileops.delete_empty_folders, body["paths"])


@app.post("/api/organize/preview")
def organize_preview(body: dict = Body(...)):
    try:
        dest = fileops.safe_path(body["dest"], allow_root=True)
    except fileops.OpError as e:
        err(e)
    where, p = queries.build_where(body.get("filter") or {})
    rows = db.conn().execute(f"SELECT id, path, ts, cat, ext FROM files{where}", p).fetchall()
    plan = fileops.organize_plan(rows, dest, body.get("pattern", "{yyyy}/{mm}"))
    return {"count": len(plan), "sample": [{"from": s, "to": d} for _, s, d in plan[:300]]}


@app.post("/api/organize/run")
def organize_run(body: dict = Body(...)):
    dest = fileops.safe_path(body["dest"], allow_root=True)
    where, p = queries.build_where(body.get("filter") or {})
    rows = db.conn().execute(f"SELECT id, path, ts, cat, ext FROM files{where}", p).fetchall()
    plan = fileops.organize_plan(rows, dest, body.get("pattern", "{yyyy}/{mm}"))
    return submit_op(f"Organize {len(plan):,} files", fileops.organize, plan, reindex=True)


# ---------------------------------------------------------------- recycle bin

@app.get("/api/trash")
def trash(limit: int = 500, offset: int = 0, q: str = ""):
    c = db.conn()
    w, p = ("", [])
    if q:
        w, p = " WHERE lower(orig_path) LIKE ?", [f"%{q.lower()}%"]
    tot = c.execute(f"SELECT COUNT(*), COALESCE(SUM(size),0) FROM trash{w}", p).fetchone()
    rows = [dict(r) for r in c.execute(f"SELECT * FROM trash{w} ORDER BY deleted_at DESC, id LIMIT ? OFFSET ?",
                                       p + [limit, offset])]
    return {"total": tot[0], "total_size": tot[1], "items": rows, "retention_days": TRASH_RETENTION_DAYS}


@app.post("/api/trash/restore")
def trash_restore(body: dict = Body(...)):
    ids = body.get("ids") or [r[0] for r in db.conn().execute("SELECT id FROM trash")]
    return submit_op(f"Restore {len(ids):,} items", fileops.restore, ids, reindex=True)


@app.post("/api/trash/empty")
def trash_empty(body: dict = Body(default={})):
    ids = body.get("ids")
    return submit_op("Empty recycle bin" if not ids else f"Permanently delete {len(ids):,} items",
                     fileops.empty_trash, ids)


@app.get("/api/trash/thumb/{tid}")
def trash_thumb(tid: int, s: int = 256):
    r = db.conn().execute("SELECT trash_path FROM trash WHERE id=?", (tid,)).fetchone()
    if not r:
        raise HTTPException(404)
    ext = scanner.split_ext(pp.basename(r[0]))
    out = thumbs.render(r[0], ext, 256) if ext in DECODABLE or ext in VIDEO_THUMB else None
    if not out:
        raise HTTPException(415)
    return FileResponse(out, media_type="image/webp")


# ---------------------------------------------------------------- bookmarks / prefs

@app.get("/api/prefs")
def prefs_get():
    return json.loads(db.kv_get("prefs", "{}"))


@app.put("/api/prefs")
def prefs_put(body: dict = Body(...)):
    db.kv_set("prefs", json.dumps(body))
    return {"ok": True}


# ---------------------------------------------------------------- web UI

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB_DIR / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
