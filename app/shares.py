"""Share links: a read-only page of chosen photos and videos that works without signing in, until it expires.

Only a hash of each link's secret is stored, so the database alone cannot recreate a link. A link shows only the
files picked when it was made (by position, never by path), and each request re-checks that the file still exists
and is still inside the library. Links work wherever SuperGallery itself is reachable; remote access still needs
two-step verification to be on.
"""
import hashlib
import json
import mimetypes
import os
import posixpath as pp
import secrets
import time

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse

from . import db, fileops, queries, scope, thumbs
from .config import DECODABLE, VIDEO_THUMB, WEB_DIR

router = APIRouter()
MAX_ITEMS = 1000
DAYS = (1, 7, 30)
SCHEMA = """
CREATE TABLE IF NOT EXISTS shares(id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 file_ids TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, views INTEGER NOT NULL DEFAULT 0);
"""


def init():
    db.conn().executescript(SCHEMA)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(ids: list[int], title: str, days: int) -> dict:
    if days not in DAYS:
        raise HTTPException(400, 'Choose 1, 7 or 30 days.')
    title = (str(title or '').strip() or 'Shared photos')[:80]
    wanted = list(dict.fromkeys(int(i) for i in ids))[:MAX_ITEMS + 1]
    if not wanted:
        raise HTTPException(400, 'Choose the photos to share.')
    if len(wanted) > MAX_ITEMS:
        raise HTTPException(400, f'Share at most {MAX_ITEMS:,} files in one link.')
    # Only files the person can see right now, in the order chosen; photos, videos and PDFs only.
    allowed = {r['id'] for r in queries.query({'ids': wanted, 'cat': ['image', 'video']}, limit=len(wanted))['items']}
    files = [i for i in wanted if i in allowed]
    if not files:
        raise HTTPException(400, 'Only photos and videos can be shared.')
    token = secrets.token_urlsafe(32)
    now = time.time()
    with db.tx() as c:
        sid = c.execute('INSERT INTO shares(token_hash,title,file_ids,created,expires) VALUES(?,?,?,?,?)',
                        (_hash(token), title, json.dumps(files), now, now + days * 86400)).lastrowid
    return {'id': sid, 'token': token, 'path': f'/s/{token}', 'count': len(files), 'expires': now + days * 86400}


def listing() -> list[dict]:
    now = time.time()
    rows = db.conn().execute('SELECT id,title,file_ids,created,expires,revoked,views FROM shares ORDER BY created DESC LIMIT 200').fetchall()
    return [{'id': r['id'], 'title': r['title'], 'count': len(json.loads(r['file_ids'])), 'created': r['created'], 'expires': r['expires'],
             'active': not r['revoked'] and r['expires'] > now, 'views': r['views']} for r in rows]


def revoke(share_id: int) -> dict:
    with db.tx() as c:
        n = c.execute('UPDATE shares SET revoked=1 WHERE id=?', (int(share_id),)).rowcount
    if not n:
        raise HTTPException(404, 'This link no longer exists.')
    return {'ok': True}


def _share(token: str):
    if not token or len(token) > 100:
        raise HTTPException(404, 'This link is not valid.')
    r = db.conn().execute('SELECT * FROM shares WHERE token_hash=?', (_hash(token),)).fetchone()
    if not r or r['revoked'] or r['expires'] <= time.time():
        raise HTTPException(404, 'This link has expired or was turned off.')
    return r


def _items(share) -> list[dict]:
    ids = json.loads(share['file_ids'])
    if not ids:
        return []
    rows = {r['id']: r for r in db.conn().execute(
        f"SELECT id,path,name,ext,cat,width,height,ts,size,duration FROM files WHERE id IN ({','.join('?' * len(ids))})", ids)}
    return [rows[i] for i in ids if i in rows]  # deleted files simply drop out


def _file(token: str, index: int):
    items = _items(_share(token))
    if not 0 <= index < len(items):
        raise HTTPException(404, 'This photo is no longer shared.')
    row = items[index]
    try:
        path = fileops.safe_path(row['path'])
    except fileops.OpError:
        raise HTTPException(404, 'This photo is no longer shared.')
    if not os.path.isfile(path):
        raise HTTPException(404, 'This photo is no longer shared.')
    return row, path


@router.get('/api/public/{token}')
def public_listing(token: str):
    share = _share(token)
    with db.tx() as c:
        c.execute('UPDATE shares SET views=views+1 WHERE id=?', (share['id'],))
    return {'title': share['title'], 'expires': share['expires'],
            'items': [{'i': n, 'name': r['name'], 'cat': r['cat'], 'ext': r['ext'], 'width': r['width'], 'height': r['height'],
                       'ts': r['ts'], 'size': r['size'], 'duration': r['duration']} for n, r in enumerate(_items(share))]}


@router.get('/api/public/{token}/thumb/{index}')
def public_thumb(token: str, index: int, s: int = 512):
    row, path = _file(token, index)
    size = 256 if s <= 256 else 512 if s <= 512 else 1600
    out = thumbs.render(path, row['ext'], size) if row['ext'] in DECODABLE or row['ext'] in VIDEO_THUMB else None
    if not out:
        raise HTTPException(415, 'No preview for this file.')
    return FileResponse(out, media_type='image/webp', headers={'Cache-Control': 'private, max-age=3600'})


@router.get('/api/public/{token}/file/{index}')
def public_file(token: str, index: int, download: bool = False):
    row, path = _file(token, index)
    mt = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    inline = mt in {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'} or mt.startswith(('video/', 'audio/'))
    return FileResponse(path, media_type=mt, filename=row['name'] or pp.basename(path),
                        content_disposition_type='inline' if inline and not download else 'attachment',
                        headers={'Content-Security-Policy': "sandbox; default-src 'none'", 'Cache-Control': 'private, max-age=3600'})


@router.get('/s/{token}')
def share_page(token: str):
    # An expired or turned-off link still gets the page (with a 404 status), which explains what happened.
    try:
        _share(token)
        status = 200
    except HTTPException:
        status = 404
    return FileResponse(WEB_DIR / 'share.html', status_code=status,
                        headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Robots-Tag': 'noindex'})


@router.post('/api/shares')
def share_create(request: Request, body: dict = Body(...)):
    ids = body.get('ids') or []
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise HTTPException(400, 'Choose the photos to share.')
    out = create(ids, body.get('title', ''), int(body.get('days', 7)))
    out['url'] = str(request.base_url).rstrip('/') + out['path']
    return out


@router.get('/api/shares')
def share_list():
    return {'shares': listing()}


@router.post('/api/shares/{share_id}/revoke')
def share_revoke(share_id: int):
    return revoke(share_id)
