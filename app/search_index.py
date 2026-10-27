"""Bounded local document text indexing and Drive-style query operators."""
import datetime as dt
import json
import re
import shlex
import subprocess
import sys
import time

from fastapi import HTTPException
from . import db, features, fileops, jobs, scope

EXTENSIONS = ("pdf", "docx", "txt", "md", "csv", "json", "html", "xml")
SCHEMA = """
CREATE TABLE IF NOT EXISTS text_index(file_id INTEGER PRIMARY KEY, path TEXT, mtime REAL, size INTEGER,
 state TEXT NOT NULL, characters INTEGER NOT NULL, updated REAL NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS document_text USING fts5(body, tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS remove_deleted_document_text AFTER DELETE ON files BEGIN
 DELETE FROM document_text WHERE rowid=OLD.id;
 DELETE FROM text_index WHERE file_id=OLD.id;
END;
"""


def init():
    db.conn().executescript(SCHEMA)
    from . import ocr_index
    ocr_index.init()


def index(task, owners=None, retry=False):
    scope.set_owners(owners)
    try:
        where, params = scope.where("f.owner", "f.ext IN (" + ",".join("?" for _ in EXTENSIONS) + ")", list(EXTENSIONS))
        rows = jobs.index_batch(task, "SELECT f.* FROM files f LEFT JOIN text_index i ON i.file_id=f.id" + where +
            " AND (i.file_id IS NULL OR i.path!=f.path OR i.mtime!=f.mtime OR i.size!=f.size" +
            (" OR i.state='error'" if retry else "") + ") ORDER BY f.mtime DESC", params)
        errors = indexed = 0
        for n, row in enumerate(rows):
            task.progress(total=len(rows), done=n, stage="Indexing document text", message=f"{n:,} of {len(rows):,} documents checked")
            text, state = "", "done"
            if row["size"] > 10 * 1024 * 1024:
                state = "too_large"
            else:
                try:
                    path = fileops.safe_path(row["path"])
                    result = subprocess.run([sys.executable, "-m", "app.extract_text", path, row["ext"]],
                        capture_output=True, timeout=20, check=True)
                    text = json.loads(result.stdout)["text"][:100_000]
                    if not text.strip():
                        state = "no_text"
                except (ValueError, KeyError, OSError, subprocess.SubprocessError, fileops.OpError):
                    state, errors = "error", errors + 1
            task.progress()
            with db.tx() as c:
                current = c.execute("SELECT path,mtime,size FROM files WHERE id=?", (row["id"],)).fetchone()
                if not current or tuple(current) != (row["path"], row["mtime"], row["size"]):
                    continue
                c.execute("DELETE FROM document_text WHERE rowid=?", (row["id"],))
                if text:
                    c.execute("INSERT INTO document_text(rowid,body) VALUES(?,?)", (row["id"], text))
                    indexed += 1
                c.execute("INSERT OR REPLACE INTO text_index VALUES(?,?,?,?,?,?,?)", (row["id"], row["path"],
                    row["mtime"], row["size"], state, len(text), time.time()))
        task.progress(done=len(rows), total=len(rows), stage="Ready", message=f"{indexed:,} documents searchable")
        return {"documents": indexed, "errors": errors}
    finally:
        scope.set_owners(None)


def status():
    where, params = scope.where("f.owner", "f.ext IN (" + ",".join("?" for _ in EXTENSIONS) + ")", list(EXTENSIONS))
    r = db.conn().execute("SELECT COUNT(*) total,SUM(i.state='done') AS \"indexed\", SUM(i.state IS NOT NULL) checked,"
        "SUM(i.state='error') errors,SUM(i.state IN ('too_large','no_text')) skipped FROM files f LEFT JOIN text_index i "
        "ON i.file_id=f.id AND i.path=f.path AND i.mtime=f.mtime AND i.size=f.size" + where, params).fetchone()
    return {**{k: r[k] or 0 for k in r.keys()}, "task": next((t for t in jobs.history()
        if t["kind"] == "documents" and t["status"] in ("queued", "running")), None)}


def clear():
    if jobs.intelligence.busy_with("documents"):
        raise HTTPException(409, "Pause document indexing before clearing its data")
    where, params = scope.where()
    with db.tx() as c:
        if not scope.owners():
            c.execute("DELETE FROM document_text")
            c.execute("DELETE FROM text_index")
        else:
            c.execute("DELETE FROM document_text WHERE rowid IN (SELECT id FROM files" + where + ")", params)
            c.execute("DELETE FROM text_index WHERE file_id IN (SELECT id FROM files" + where + ")", params)
    return {"ok": True}


def parse(text):
    if not isinstance(text, str) or len(text) > 500:
        raise HTTPException(400, "Keep searches under 500 characters")
    try:
        tokens = shlex.split(text)
    except ValueError:
        raise HTTPException(400, "Close the quotation mark to search a phrase")
    filters, words, labels = {}, [], []
    types = {"photo": "image", "photos": "image", "image": "image", "video": "video", "videos": "video",
             "audio": "audio", "music": "audio", "document": "document", "documents": "document", "folder": None}
    for token in tokens:
        key, sep, value = token.partition(":")
        key = key.lower()
        if not sep or key not in {"type", "owner", "person", "before", "after", "in", "name", "larger", "smaller"}:
            words.append(token)
            continue
        if not value:
            raise HTTPException(400, f"Add a value after {key}:")
        if key == "type":
            value = value.lower().lstrip(".")
            if value in types and types[value]:
                filters["cat"] = [types[value]]
            elif re.fullmatch(r"[a-z0-9]{1,12}", value) and value != "folder":
                filters["ext"] = [value]
            else:
                raise HTTPException(400, "Choose a file type, such as photo, video or pdf")
        elif key in ("before", "after"):
            try:
                filters[key] = dt.datetime.combine(dt.date.fromisoformat(value), dt.time(), dt.timezone.utc).timestamp()
            except ValueError:
                raise HTTPException(400, "Use dates like after:2025-01-01")
        elif key in ("larger", "smaller"):
            m = re.fullmatch(r"(\d+(?:\.\d+)?)(b|kb|mb|gb|tb)?", value, re.I)
            if not m:
                raise HTTPException(400, "Use a size like larger:10MB")
            filters["min_size" if key == "larger" else "max_size"] = int(float(m[1]) * 1024 ** ["b", "kb", "mb", "gb", "tb"].index((m[2] or "b").lower()))
        else:
            filters[{"owner": "owner", "person": "person_name", "name": "q", "in": "path_q"}[key]] = value
        labels.append({"key": key, "value": value})
    if words:
        filters["text"] = " ".join(words)
    return {"filter": filters, "labels": labels}


def text_condition(text):
    """A literal query, never raw FTS syntax. Matches names, folders, people or extracted text."""
    words = str(text)[:500].strip().split()[:30]
    if not words:
        return "1", []
    def pattern(word):
        return "%" + word.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    clauses, params = [], []
    for field in ("lower(name)", "lower(path)"):
        clauses.append("(" + " AND ".join(field + " LIKE ? ESCAPE '\\'" for _ in words) + ")")
        params += [pattern(w) for w in words]
    if features.enabled('people'):
        clauses.append("id IN (SELECT cf.file_id FROM current_faces cf JOIN people p ON p.id=cf.person_id WHERE cf.ignored=0 AND " +
            " AND ".join("lower(p.name) LIKE ? ESCAPE '\\'" for _ in words) + ")")
        params += [pattern(w) for w in words]
    terms = re.findall(r"\w+", " ".join(words), re.UNICODE)
    if terms and features.enabled('documents'):
        clauses.append("id IN (SELECT t.file_id FROM document_text JOIN text_index t ON t.file_id=document_text.rowid "
            "JOIN files fresh ON fresh.id=t.file_id AND fresh.path=t.path AND fresh.mtime=t.mtime AND fresh.size=t.size "
            "WHERE document_text MATCH ?)")
        params.append(" AND ".join('"' + word + '"*' for word in terms))
    if terms and features.enabled('ocr'):
        clauses.append("id IN (SELECT o.file_id FROM ocr_text JOIN ocr_index o ON o.file_id=ocr_text.rowid "
            "JOIN files fresh ON fresh.id=o.file_id AND fresh.path=o.path AND fresh.mtime=o.mtime AND fresh.size=o.size "
            "WHERE ocr_text MATCH ?)")
        params.append(" AND ".join('"' + word + '"*' for word in terms))
    return "(" + " OR ".join(clauses) + ")", params
