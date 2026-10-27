"""Verified app-data snapshots and restart-safe restore. Never copies original media."""
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import time
import zipfile
import tempfile
from contextlib import closing
from pathlib import Path
from fastapi import HTTPException
from .config import CONFIG_DIR


def root():
    path=CONFIG_DIR/'library-backups'
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    return path


def pending():
    return (CONFIG_DIR/'restore-request.json').exists()


def snapshot(task=None, label='Manual backup'):
    backup_id=time.strftime('%Y%m%d-%H%M%S',time.gmtime())+'-'+secrets.token_hex(3)
    destination=root()/backup_id
    destination.mkdir(mode=0o700)
    path=destination/'index.db'
    if task:task.progress(stage='Backing up app data',message='Copying a consistent database snapshot')
    try:
        with closing(sqlite3.connect(CONFIG_DIR/'index.db')) as source, closing(sqlite3.connect(path)) as target:
            source.backup(target,pages=1024,sleep=.01)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise RuntimeError('Backup integrity check failed')
            count=target.execute('SELECT COUNT(*) FROM files').fetchone()[0]
        path.chmod(0o600)
        with path.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        manifest={'id':backup_id,'created':time.time(),'label':label,'bytes':path.stat().st_size,'files':count,
            'sha256':digest,'verified':True,'originals_included':False,'version':1}
        (destination/'manifest.json').write_text(json.dumps(manifest,indent=2))
        (destination/'manifest.json').chmod(0o600)
        if task:task.progress(stage='Verified',done=1,total=1,message='App data backup passed its integrity check')
        return manifest
    except Exception:
        # Incomplete snapshots are not listed or restorable.
        raise


def resolve(backup_id):
    if not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}',backup_id):
        raise HTTPException(400,'Choose a valid app backup.')
    path=(root()/backup_id).resolve()
    if path.parent!=root().resolve() or path.is_symlink():
        raise HTTPException(400,'Invalid backup path.')
    return path


def listing():
    items=[]
    for path in root().glob('*/manifest.json'):
        try:
            manifest=json.loads(path.read_text())
            resolve(manifest['id'])
            items.append(manifest)
        except (ValueError,KeyError,OSError,HTTPException):
            continue
    return {'items':sorted(items,key=lambda x:x['created'],reverse=True),'restore_pending':pending()}


def verify(backup_id):
    path=resolve(backup_id)
    try:
        manifest=json.loads((path/'manifest.json').read_text())
        with (path/'index.db').open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['sha256']:
                raise ValueError('Checksum mismatch')
        with closing(sqlite3.connect((path/'index.db').as_uri()+'?mode=ro',uri=True)) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Integrity check failed')
            required={'files','kv','trash','people','faces','smart_albums'}
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables):raise ValueError('Unsupported snapshot')
        return manifest
    except (OSError,ValueError,KeyError,sqlite3.Error):
        raise HTTPException(409,'This backup failed validation. No changes were made.')


def stage(backup_id):
    from . import jobs
    if any(t['status'] in ('queued','running') for t in jobs.history()):
        raise HTTPException(409,'Pause indexing and wait for file operations to finish before restoring.')
    verify(backup_id)
    marker=CONFIG_DIR/'restore-request.json'
    temporary=CONFIG_DIR/'restore-request.tmp'
    temporary.write_text(json.dumps({'id':backup_id,'requested':time.time()}));temporary.chmod(0o600)
    os.replace(temporary,marker)
    return {'ok':True,'restart_required':True}


def export(backup_id):
    manifest=verify(backup_id)
    folder=resolve(backup_id)
    archive=folder/'supergallery-app-data.zip'
    if archive.exists():return archive
    if shutil.disk_usage(folder).free<manifest['bytes']+16*1024**2:
        raise HTTPException(507,'Not enough NAS space to prepare the backup download.')
    fd,name=tempfile.mkstemp(prefix='export-',suffix='.tmp',dir=folder)
    os.close(fd)
    try:
        with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_STORED) as z:
            z.write(folder/'index.db','index.db')
            z.write(folder/'manifest.json','manifest.json')
        os.replace(name,archive)
    finally:
        Path(name).unlink(missing_ok=True)
    return archive


def cancel():
    (CONFIG_DIR/'restore-request.json').unlink(missing_ok=True)
    return {'ok':True}


def apply_pending():
    """Runs before the application's database connections or jobs are opened."""
    marker=CONFIG_DIR/'restore-request.json'
    if not marker.exists():return
    backup_id=json.loads(marker.read_text())['id']
    verify(backup_id)
    snapshot(label='Before restore')
    temporary=CONFIG_DIR/'index.restore.db'
    shutil.copyfile(resolve(backup_id)/'index.db',temporary)
    with closing(sqlite3.connect(CONFIG_DIR/'index.db')) as current, closing(sqlite3.connect(temporary)) as restored:
        # File moves/deletions aren't undone by metadata restore. Keep the current
        # recycle-bin ledger so the user can still restore actual originals.
        for table in ('trash','deletion_log'):
            rows=current.execute('SELECT * FROM '+table).fetchall()
            restored.execute('DELETE FROM '+table)
            if rows:restored.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in rows[0])+')',rows)
        restored.execute("DELETE FROM kv WHERE k='last_scan'")
        restored.execute("INSERT OR REPLACE INTO kv(k,v) VALUES('rules','[]')")
        restored.execute("UPDATE intelligence_requests SET state='paused' WHERE state IN ('queued','running')")
        restored.commit()
        if restored.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Restore verification failed')
        current.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    # All DB handles are closed here. Credentials and TLS files are untouched.
    for suffix in ('-wal','-shm'):
        (CONFIG_DIR/('index.db'+suffix)).unlink(missing_ok=True)
    temporary.chmod(0o600);os.replace(temporary,CONFIG_DIR/'index.db')
    marker.unlink()
