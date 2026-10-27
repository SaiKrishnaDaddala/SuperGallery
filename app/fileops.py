"""File operations. Deletes go to a per-volume recycle bin by default so every bulk action is undoable."""
import os
import posixpath as pp
import shutil
import time

from . import db, scanner, scope
from .config import SCAN_ROOTS, TRASH_NAME, TRASH_RETENTION_DAYS, fwd


class OpError(Exception):
    pass


def safe_path(p: str, allow_root: bool = False) -> str:
    """Resolve p and make sure it lives inside a scan root (and not inside the recycle bin)."""
    if not p:
        raise OpError("empty path")
    rp = fwd(os.path.realpath(p))
    root = scanner.root_of(rp)
    if root is None:
        raise OpError(f"outside the NAS folders: {p}")
    if rp == root and not allow_root:
        raise OpError("refusing to modify a top-level volume")
    if f"/{TRASH_NAME}/" in rp[len(root):] + "/":
        raise OpError("path is inside the recycle bin")
    return rp


def _move(src: str, dst: str):
    os.makedirs(pp.dirname(dst), exist_ok=True)
    try:
        os.rename(src, dst)  # instant on the same volume
    except OSError:
        shutil.move(src, dst)


def unique_dest(dst: str) -> str:
    if not os.path.lexists(dst):
        return dst
    base, ext = pp.splitext(dst)
    i = 1
    while os.path.lexists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def resolve_targets(ids=None, paths=None) -> list[tuple[str, int, bool]]:
    """-> [(path, size, is_dir)] for ids from the index and/or raw paths (file manager)."""
    out = []
    c = db.conn()
    if ids:
        for i in range(0, len(ids), 900):
            part = ids[i:i + 900]
            q = f"SELECT path, size FROM files WHERE id IN ({','.join('?' * len(part))})"
            out.extend((r[0], r[1], False) for r in c.execute(q, part))
    for p in paths or []:
        rp = safe_path(p)
        if os.path.isdir(rp) and not os.path.islink(rp):
            r = c.execute("SELECT size FROM folders WHERE path=?", (rp,)).fetchone()
            out.append((rp, r[0] if r else 0, True))
        elif os.path.lexists(rp):
            out.append((rp, os.lstat(rp).st_size, False))
    return out


def trash_base(path: str) -> str:
    """Recycle bin lives in the top-level shared folder of each file. On UGOS/Btrfs every shared
    folder is its own subvolume, so a per-share bin keeps "delete" an instant rename (no copying)."""
    root = scanner.root_of(path)
    rel = path[len(root) + 1:]
    top = rel.split("/", 1)[0]
    return pp.join(root, top) if "/" in rel else root


def guard_keep_one(ids: list[int], mode: str) -> list[int]:
    """Drop ids that would delete every copy of a duplicate set / every photo of a similar group.

    Modes: "dupes" / "similar" keep one per user; "dupes_all" / "similar_all" keep one overall."""
    c = db.conn()
    idset = set(ids)
    sql = {
        "dupes": "SELECT id, hash||'|'||owner FROM files WHERE hash IN (SELECT hash FROM files WHERE id IN ({}))",
        "dupes_all": "SELECT id, hash FROM files WHERE hash IN (SELECT hash FROM files WHERE id IN ({}))",
        "similar": """SELECT g.file_id, g.gid||'|'||f.owner FROM sim_groups g JOIN files f ON f.id=g.file_id
                      WHERE g.gid IN (SELECT gid FROM sim_groups WHERE file_id IN ({}))""",
        "similar_all": """SELECT g.file_id, g.gid FROM sim_groups g
                          WHERE g.gid IN (SELECT gid FROM sim_groups WHERE file_id IN ({}))""",
    }.get(mode)
    if not sql:
        return ids
    groups: dict = {}
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        for r in c.execute(sql.format(",".join("?" * len(part))), part):
            groups.setdefault(r[1], set()).add(r[0])
    blocked = set()
    for members in groups.values():
        if len(members) > 1 and members <= idset:  # a file with no other copy isn't a duplicate set
            blocked.add(min(members))  # spare one file of the group
    return [i for i in ids if i not in blocked]


def _meta(paths: list[str]) -> dict:
    out = {}
    c = db.conn()
    for i in range(0, len(paths), 900):
        part = paths[i:i + 900]
        for r in c.execute(f"SELECT path, owner, cat, kind, ext, dir FROM files WHERE path IN "
                           f"({','.join('?' * len(part))})", part):
            out[r[0]] = (r[1], r[2], r[3], r[4], r[5])
    return out


def delete(task, ids=None, paths=None, permanent=False, guard=None, reason=None):
    if ids and guard:
        ids = guard_keep_one(ids, guard)
    targets = resolve_targets(ids, paths)
    task.progress(0, len(targets), stage="Deleting" if permanent else "Moving to recycle bin")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    meta = _meta([t[0] for t in targets if not t[2]])
    done_files, trash_rows, log_rows, errors, freed = [], [], [], [], 0
    for i, (path, size, is_dir) in enumerate(targets):
        try:
            safe_path(path)
            if reason == 'duplicates' and guard in ('dupes','dupes_all'):
                verify_duplicate_survivor(path, set(ids or []), guard == 'dupes')
            if permanent:
                if is_dir:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            else:
                base = trash_base(path)
                dst = unique_dest(pp.join(base, TRASH_NAME, stamp, path[len(base) + 1:]))
                _move(path, dst)
                m = meta.get(path) or (scope.owner_of(path), None, None, None, None)
                trash_rows.append((path, dst, size, int(is_dir), time.time(), reason, m[0], m[1], m[2]))
            freed += size
            if not is_dir:
                m = meta.get(path) or (scope.owner_of(path), None, None, None, None)
                log_rows.append((time.time(), m[0], m[1], m[2], m[3], m[4], size, reason))
            if is_dir:
                scanner.forget_folder(path)
            else:
                done_files.append((path, size))
        except (OSError, OpError) as e:
            errors.append(f"{path}: {e}")
        if len(done_files) >= 500:
            _commit(done_files, trash_rows, log_rows)
        if i % 50 == 0:
            task.progress(i)
    _commit(done_files, trash_rows, log_rows)
    task.progress(len(targets))
    return {"deleted": len(targets) - len(errors), "freed": freed, "errors": errors[:50],
            "error_count": len(errors), "permanent": permanent}


def verify_duplicate_survivor(path, deleting, per_user=True):
    """Fail closed when a duplicate or its keeper changed after the library scan."""
    row=db.conn().execute('SELECT id,path,size,mtime,hash,owner FROM files WHERE path=?',(path,)).fetchone()
    if not row or not row['hash']:
        raise OpError('This duplicate needs to be scanned again before recycling.')
    def unchanged(item):
        try:
            st=os.stat(safe_path(item['path']))
            return st.st_size==item['size'] and abs(st.st_mtime-item['mtime'])<.001
        except (OSError,OpError):
            return False
    if not unchanged(row):
        raise OpError('This file changed after scanning. Rescan before recycling it.')
    candidates=db.conn().execute('SELECT id,path,size,mtime FROM files WHERE hash=?'+(' AND owner=?' if per_user else ''),
        [row['hash']]+([row['owner']] if per_user else [])).fetchall()
    if not any(item['id'] not in deleting and unchanged(item) for item in candidates):
        raise OpError('No unchanged copy can be kept. This file was left in place.')


def _commit(done_files, trash_rows, log_rows):
    if done_files:
        scanner.forget_files(done_files)
        done_files.clear()
    with db.tx() as t:
        if trash_rows:
            t.executemany("INSERT INTO trash(orig_path, trash_path, size, is_dir, deleted_at, reason, owner, cat, kind) "
                          "VALUES(?,?,?,?,?,?,?,?,?)", trash_rows)
        if log_rows:
            t.executemany("INSERT INTO deletion_log(ts, owner, cat, kind, ext, dir, size, reason) "
                          "VALUES(?,?,?,?,?,?,?,?)", log_rows)
    trash_rows.clear()
    log_rows.clear()


def move(task, dest: str, ids=None, paths=None, copy=False):
    dest = safe_path(dest, allow_root=True)
    if not os.path.isdir(dest):
        raise OpError("destination folder does not exist")
    targets = resolve_targets(ids, paths)
    task.progress(0, len(targets), stage="Copying" if copy else "Moving")
    errors, moved = [], []
    for i, (path, size, is_dir) in enumerate(targets):
        try:
            if is_dir and (dest == path or dest.startswith(path + "/")):
                raise OpError("cannot move a folder into itself")
            dst = unique_dest(pp.join(dest, pp.basename(path)))
            if copy:
                (shutil.copytree if is_dir else shutil.copy2)(path, dst)
            else:
                _move(path, dst)
                if is_dir:
                    scanner.move_folder(path, dst)
                else:
                    moved.append((path, size))
            if not is_dir:
                scanner.index_file(dst)
        except (OSError, OpError) as e:
            errors.append(f"{path}: {e}")
        if i % 50 == 0:
            task.progress(i)
    if moved:
        scanner.forget_files(moved)
    task.progress(len(targets))
    return {"moved": len(targets) - len(errors), "errors": errors[:50], "error_count": len(errors)}


def rename(path: str, new_name: str) -> str:
    path = safe_path(path)
    if not new_name or "/" in new_name or new_name in (".", ".."):
        raise OpError("invalid name")
    dst = pp.join(pp.dirname(path), new_name)
    if os.path.lexists(dst):
        raise OpError("a file with that name already exists")
    is_dir = os.path.isdir(path)
    size = 0 if is_dir else os.lstat(path).st_size
    os.rename(path, dst)
    if is_dir:
        scanner.move_folder(path, dst)
    else:
        scanner.forget_files([(path, size)])
        scanner.index_file(dst)
    return dst


def mkdir(parent: str, name: str) -> str:
    parent = safe_path(parent, allow_root=True)
    if not name or "/" in name:
        raise OpError("invalid name")
    p = pp.join(parent, name)
    os.makedirs(p, exist_ok=False)
    with db.tx() as t:
        scanner.ensure_folders(t, pp.join(p, "x"))
    return p


def delete_empty_folders(task, paths: list[str]):
    """Remove folders that contain no files at all (deepest first)."""
    ok, errors = 0, []
    task.progress(0, len(paths), stage="Removing empty folders")
    for i, p in enumerate(sorted(paths, key=len, reverse=True)):
        try:
            p = safe_path(p)
            for dirpath, _dirs, files in os.walk(p, topdown=False):
                dirpath = fwd(dirpath)
                if files:
                    raise OpError("folder is not empty anymore")
                os.rmdir(dirpath)
            db.conn().execute("DELETE FROM folders WHERE path=?", (p,))
            ok += 1
        except (OSError, OpError) as e:
            errors.append(f"{p}: {e}")
        task.progress(i + 1)
    return {"deleted": ok, "errors": errors[:50], "error_count": len(errors)}


def restore(task, trash_ids: list[int]):
    c = db.conn()
    rows = []
    for i in range(0, len(trash_ids), 900):
        part = trash_ids[i:i + 900]
        rows += c.execute(f"SELECT id, orig_path, trash_path, is_dir FROM trash WHERE id IN "
                          f"({','.join('?' * len(part))})", part).fetchall()
    task.progress(0, len(rows), stage="Restoring")
    errors, ok = [], []
    for n, (tid, orig, tpath, is_dir) in enumerate(rows):
        try:
            dst = unique_dest(orig)
            _move(tpath, dst)
            if not is_dir:
                scanner.index_file(dst)
            ok.append((tid,))
        except OSError as e:
            errors.append(f"{orig}: {e}")
        if n % 50 == 0:
            task.progress(n)
    with db.tx() as t:
        t.executemany("DELETE FROM trash WHERE id=?", ok)
    _prune_empty_trash_dirs()
    return {"restored": len(ok), "errors": errors[:50], "error_count": len(errors)}


def empty_trash(task, trash_ids: list[int] | None = None, older_than_days: float | None = None):
    c = db.conn()
    if trash_ids:
        rows = []
        for i in range(0, len(trash_ids), 900):
            part = trash_ids[i:i + 900]
            rows += c.execute(f"SELECT id, trash_path, is_dir, size FROM trash WHERE id IN "
                              f"({','.join('?' * len(part))})", part).fetchall()
    elif older_than_days is not None:
        rows = c.execute("SELECT id, trash_path, is_dir, size FROM trash WHERE deleted_at<?",
                         (time.time() - older_than_days * 86400,)).fetchall()
    else:
        rows = c.execute("SELECT id, trash_path, is_dir, size FROM trash").fetchall()
    task.progress(0, len(rows), stage="Emptying recycle bin")
    gone, freed = [], 0
    for n, (tid, tpath, is_dir, size) in enumerate(rows):
        try:
            if is_dir:
                shutil.rmtree(tpath)
            else:
                os.remove(tpath)
        except FileNotFoundError:
            pass
        except OSError:
            continue
        gone.append((tid,))
        freed += size
        if n % 100 == 0:
            task.progress(n)
    with db.tx() as t:
        t.executemany("DELETE FROM trash WHERE id=?", gone)
    _prune_empty_trash_dirs()
    return {"purged": len(gone), "freed": freed}


def purge_old_trash(task):
    return empty_trash(task, older_than_days=TRASH_RETENTION_DAYS)


def _prune_empty_trash_dirs():
    bins = []
    for root in SCAN_ROOTS:
        bins.append(pp.join(root, TRASH_NAME))
        try:
            bins += [pp.join(root, e.name, TRASH_NAME) for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
        except OSError:
            pass
    for t in bins:
        if not os.path.isdir(t):
            continue
        for dirpath, _dirs, files in os.walk(t, topdown=False):
            dirpath = fwd(dirpath)
            if not files:
                try:
                    os.rmdir(dirpath)  # also removes the bin itself once empty
                except OSError:
                    pass


def organize_plan(rows, dest_root: str, pattern: str):
    """rows: (id, path, ts, cat, ext) -> [(id, src, dst)] moves using {yyyy} {mm} {dd} {cat} {ext} tokens."""
    plan = []
    for fid, path, ts, cat, ext in rows:
        t = time.localtime(ts)
        sub = (pattern.replace("{yyyy}", f"{t.tm_year:04d}").replace("{mm}", f"{t.tm_mon:02d}")
               .replace("{dd}", f"{t.tm_mday:02d}").replace("{cat}", cat).replace("{ext}", ext or "noext"))
        dst = pp.join(dest_root, sub.strip("/"), pp.basename(path))
        if dst != path:
            plan.append((fid, path, dst))
    return plan


def organize(task, plan):
    task.progress(0, len(plan), stage="Organizing files")
    moved, errors = [], []
    for n, (_fid, src, dst) in enumerate(plan):
        try:
            safe_path(src)
            dst = unique_dest(safe_path(dst, allow_root=True))
            size = os.lstat(src).st_size
            _move(src, dst)
            moved.append((src, size))
            scanner.index_file(dst)
        except (OSError, OpError) as e:
            errors.append(f"{src}: {e}")
        if n % 50 == 0:
            task.progress(n)
    if moved:
        scanner.forget_files(moved)
    task.progress(len(plan))
    return {"moved": len(moved), "errors": errors[:50], "error_count": len(errors)}


def rename_plan(paths: list[str], find: str, replace: str, mode: str = "text", start: int = 1,
                case: str | None = None) -> list[tuple[str, str]]:
    """Bulk rename preview. mode: text | regex | template ({name} {ext} {n} {n:3} {date})."""
    import re

    out = []
    rx = re.compile(find) if mode == "regex" and find else None
    for i, p in enumerate(paths):
        p = safe_path(p)
        name = pp.basename(p)
        stem, ext = pp.splitext(name)
        if mode == "template":
            n = start + i
            new = re.sub(r"\{n(?::(\d+))?\}", lambda m: str(n).zfill(int(m.group(1) or 0)), replace)
            mt = time.localtime(os.lstat(p).st_mtime)
            new = (new.replace("{name}", stem).replace("{ext}", ext.lstrip("."))
                   .replace("{date}", time.strftime("%Y-%m-%d", mt)))
            if "{ext}" not in replace and ext and not new.endswith(ext):
                new += ext
        elif rx:
            new = rx.sub(replace, name)
        else:
            new = name.replace(find, replace) if find else name
        if case == "lower":
            new = new.lower()
        elif case == "upper":
            new = new.upper()
        elif case == "title":
            s, e = pp.splitext(new)
            new = s.title() + e.lower()
        out.append((p, new))
    return out


def bulk_rename(task, plan: list[tuple[str, str]]):
    task.progress(0, len(plan), stage="Renaming")
    done, errors = 0, []
    for i, (p, new) in enumerate(plan):
        if pp.basename(p) == new:
            continue
        try:
            rename(p, new)
            done += 1
        except (OSError, OpError) as e:
            errors.append(f"{p}: {e}")
        task.progress(i + 1)
    return {"renamed": done, "errors": errors[:50], "error_count": len(errors)}


def compress(task, paths: list[str], dest_dir: str, name: str):
    import zipfile

    dest_dir = safe_path(dest_dir, allow_root=True)
    if not name.lower().endswith(".zip"):
        name += ".zip"
    out = unique_dest(pp.join(dest_dir, name))
    srcs = [safe_path(p) for p in paths]
    files = []
    for s in srcs:
        base = pp.dirname(s)
        if os.path.isdir(s):
            for dp, _ds, fs in os.walk(s):
                dp = fwd(dp)
                files.extend((pp.join(dp, f), pp.join(dp, f)[len(base) + 1:]) for f in fs)
        else:
            files.append((s, pp.basename(s)))
    task.progress(0, len(files), stage=f"Compressing to {pp.basename(out)}")
    with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for i, (fp, arc) in enumerate(files):
            try:
                z.write(fp, arc)
            except OSError:
                pass
            task.step()
    os.replace(out + ".part", out)
    scanner.index_file(out)
    return {"archive": out, "files": len(files)}


def extract(task, path: str, dest_dir: str | None = None):
    import tarfile
    import zipfile

    path = safe_path(path)
    base = pp.basename(path)
    stem = base
    for suf in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar", ".zip"):
        if base.lower().endswith(suf):
            stem = base[: -len(suf)]
            break
    target = unique_dest(pp.join(safe_path(dest_dir, allow_root=True) if dest_dir else pp.dirname(path), stem))
    os.makedirs(target)
    task.progress(0, 0, stage=f"Extracting {base}")

    def inside(p):  # block zip-slip
        rp = fwd(os.path.realpath(pp.join(target, p)))
        return rp == target or rp.startswith(target + "/")

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            members = [m for m in z.infolist() if inside(m.filename)]
            task.progress(0, len(members))
            for m in members:
                z.extract(m, target)
                task.step()
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as t:
            members = [m for m in t.getmembers() if inside(m.name) and (m.isfile() or m.isdir())]
            task.progress(0, len(members))
            for m in members:
                t.extract(m, target, filter="data")
                task.step()
    else:
        os.rmdir(target)
        raise OpError("unsupported archive (zip / tar / tar.gz supported)")
    for dp, _ds, fs in os.walk(target):
        dp = fwd(dp)
        for f in fs:
            scanner.index_file(pp.join(dp, f))
    return {"folder": target}
