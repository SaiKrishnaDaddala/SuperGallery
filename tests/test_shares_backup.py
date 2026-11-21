"""Share links show only what was shared, only while valid; phone backup skips what the NAS already has."""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app import auth_http, fileops, shares, uploads_http
from app.security import Security

from test_discovery import library  # noqa: F401  (shared fixture)

PASSWORD = 'test-only-password-123'


@pytest.fixture
def app_client(library, tmp_path, monkeypatch):  # noqa: F811
    c, add, _ = library
    shares.init()
    monkeypatch.setattr(auth_http, 'security', Security(tmp_path / 'auth', PASSWORD))
    monkeypatch.setattr(fileops, 'safe_path', lambda path, **kw: path)  # the fixture lives outside the library roots
    monkeypatch.setattr(uploads_http, 'safe_path', lambda path: path)
    app = FastAPI()
    auth_http.install(app)
    app.include_router(shares.router)
    app.include_router(uploads_http.router)
    signed_in = TestClient(app, base_url='https://nas.test', headers={'X-SG-Request': '1'})
    assert signed_in.post('/api/login', json={'password': PASSWORD}).status_code == 200
    anonymous = TestClient(app, base_url='https://nas.test')
    photos = []
    for name in ('a.jpg', 'b.jpg'):
        fid, path = add(name)
        Image.new('RGB', (40, 30), 'orange').save(path)
        st = path.stat()
        c.execute('UPDATE files SET size=?, mtime=?, width=40, height=30 WHERE id=?', (st.st_size, st.st_mtime, fid))
        photos.append((fid, path))
    doc, _ = add('notes.txt', cat='document')
    return c, signed_in, anonymous, photos, doc


def test_a_link_shows_only_its_photos_without_signing_in(app_client):
    c, signed_in, anonymous, photos, doc = app_client
    made = signed_in.post('/api/shares', json={'ids': [photos[1][0], doc], 'title': 'Trip', 'days': 7}).json()
    assert made['count'] == 1 and made['path'].startswith('/s/')  # the document is not shareable
    token = made['path'][3:]
    listing = anonymous.get(f'/api/public/{token}')
    assert listing.status_code == 200
    body = listing.json()
    assert body['title'] == 'Trip' and [i['name'] for i in body['items']] == ['b.jpg']
    assert 'path' not in body['items'][0] and str(photos[1][1].parent) not in listing.text  # no folder paths
    assert anonymous.get(f'/api/public/{token}/file/0').content == photos[1][1].read_bytes()
    assert anonymous.get(f'/api/public/{token}/file/1').status_code == 404  # nothing beyond what was shared
    page = anonymous.get(made['path'])
    assert page.status_code == 200 and "frame-ancestors 'none'" in page.headers['content-security-policy']
    assert page.headers['referrer-policy'] == 'no-referrer'


def test_expired_revoked_and_made_up_links_fail(app_client):
    c, signed_in, anonymous, photos, _ = app_client
    token = signed_in.post('/api/shares', json={'ids': [photos[0][0]], 'days': 1}).json()['path'][3:]
    assert anonymous.get(f'/api/public/{token}').status_code == 200
    assert anonymous.get('/api/public/not-a-real-link').status_code == 404
    assert anonymous.get(f'/api/public/{token[:-1]}x').status_code == 404
    c.execute('UPDATE shares SET expires=?', (time.time() - 1,))
    assert anonymous.get(f'/api/public/{token}').status_code == 404
    assert anonymous.get(f'/s/{token}').status_code == 404
    c.execute('UPDATE shares SET expires=?', (time.time() + 999,))
    sid = signed_in.get('/api/shares').json()['shares'][0]['id']
    assert signed_in.post(f'/api/shares/{sid}/revoke').status_code == 200
    assert anonymous.get(f'/api/public/{token}/thumb/0').status_code == 404
    assert signed_in.get('/api/shares').json()['shares'][0]['active'] is False


def test_only_signed_in_people_manage_links_and_viewers_cannot_change_anything(app_client):
    c, signed_in, anonymous, photos, _ = app_client
    token = signed_in.post('/api/shares', json={'ids': [photos[0][0]], 'days': 7}).json()['path'][3:]
    assert anonymous.get('/api/shares').status_code == 401
    assert anonymous.post('/api/shares', json={'ids': [photos[0][0]], 'days': 7}, headers={'X-SG-Request': '1'}).status_code == 401
    assert anonymous.post(f'/api/public/{token}', headers={'X-SG-Request': '1'}).status_code in (401, 405)
    assert signed_in.post('/api/shares', json={'ids': [photos[0][0]], 'days': 3}).status_code == 400
    assert signed_in.post('/api/shares', json={'ids': [], 'days': 7}).status_code == 400
    # a file deleted from the library drops out of the link
    c.execute('DELETE FROM files WHERE id=?', (photos[0][0],))
    assert anonymous.get(f'/api/public/{token}').json()['items'] == []
    assert hash(token) and token not in str(c.execute('SELECT * FROM shares').fetchall())  # only a fingerprint is stored


def test_phone_backup_skips_files_already_on_the_nas(app_client):
    c, signed_in, anonymous, photos, _ = app_client
    have = photos[0][1]
    from app import scope
    scope_root = have.parent.parent.as_posix()  # the fixture's people folders sit here
    import pytest as _pytest
    mp = _pytest.MonkeyPatch(); mp.setattr(scope, 'USERS_ROOT', scope_root)
    r = signed_in.post('/api/uploads/check', json={'destination': have.parent.as_posix(), 'files': [
        {'name': 'a.jpg', 'size': have.stat().st_size}, {'name': 'a.jpg', 'size': 1}, {'name': 'new.jpg', 'size': 10}]})
    mp.undo()
    assert r.status_code == 200 and r.json()['present'] == [0] and r.json()['owner'] == 'alice'
    assert anonymous.post('/api/uploads/check', json={'destination': '/', 'files': []}, headers={'X-SG-Request': '1'}).status_code == 401
