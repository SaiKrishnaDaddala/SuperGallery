"""Saved searches; their results are evaluated against the current library on opening."""
import json
import time
from fastapi import HTTPException
from . import db

MODES = {'files','photos','videos'}


def init():
    db.conn().execute('CREATE TABLE IF NOT EXISTS smart_albums(id INTEGER PRIMARY KEY,name TEXT NOT NULL,definition TEXT NOT NULL,created REAL,updated REAL)')


def listing():
    return {'items':[{**dict(r),'definition':json.loads(r['definition'])} for r in db.conn().execute('SELECT * FROM smart_albums ORDER BY name COLLATE NOCASE,id')]}


def save(name, definition, album_id=None):
    name = name.strip()
    if not name or len(name)>80 or any(ord(c)<32 for c in name):
        raise HTTPException(400,'Use an album name of 1–80 characters.')
    if definition.get('mode') not in MODES or len(definition.get('q',''))>500:
        raise HTTPException(400,'Choose a valid saved search.')
    encoded = json.dumps(definition)
    if len(encoded)>8000:
        raise HTTPException(400,'This search has too many filters.')
    if album_id:
        if not db.conn().execute('UPDATE smart_albums SET name=?,definition=?,updated=? WHERE id=?',(name,encoded,time.time(),album_id)).rowcount:
            raise HTTPException(404,'Album not found.')
    else:
        if db.conn().execute('SELECT COUNT(*) FROM smart_albums').fetchone()[0]>=200:
            raise HTTPException(409,'You can keep up to 200 smart albums.')
        album_id = db.conn().execute('INSERT INTO smart_albums(name,definition,created,updated) VALUES(?,?,?,?)',(name,encoded,time.time(),time.time())).lastrowid
    return {'id':album_id}


def remove(album_id):
    db.conn().execute('DELETE FROM smart_albums WHERE id=?',(album_id,))
    return {'ok':True}
