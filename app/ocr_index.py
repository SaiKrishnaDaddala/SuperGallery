"""Search text in images and scanned PDFs, entirely on the NAS."""
import json
import os
import queue
import subprocess
import sys
import threading
import time

from . import db, fileops, jobs, scope
from .config import DECODABLE

SCHEMA = """
CREATE TABLE IF NOT EXISTS ocr_index(file_id INTEGER PRIMARY KEY,path TEXT,mtime REAL,size INTEGER,
 state TEXT NOT NULL,pages INTEGER NOT NULL,updated REAL NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS ocr_text USING fts5(body,tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS remove_deleted_ocr AFTER DELETE ON files BEGIN
 DELETE FROM ocr_text WHERE rowid=OLD.id;
 DELETE FROM ocr_index WHERE file_id=OLD.id;
END;
"""


def init():
    db.conn().executescript(SCHEMA)


class Worker:
    def __init__(self):
        self.output = queue.Queue()
        self.process = subprocess.Popen([sys.executable, '-m', 'app.ocr_worker'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', bufsize=1)
        def read():
            for line in self.process.stdout:
                self.output.put(line)
            self.output.put(None)
        threading.Thread(target=read, daemon=True).start()

    def extract(self, path, ext, task):
        self.process.stdin.write(json.dumps({'path': path, 'ext': ext}) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            task.progress()
            try:
                line = self.output.get(timeout=.5)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError('OCR worker stopped')
            return json.loads(line)
        raise TimeoutError('OCR exceeded the per-file time limit')

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=10)
        self.process.stdin.close(); self.process.stdout.close()


def index(task, owners=None, retry=False):
    scope.set_owners(owners)
    worker = None
    try:
        where, args = scope.where('f.owner', "(f.cat='image' OR f.ext='pdf')")
        rows = jobs.index_batch(task, 'SELECT f.id,f.path,f.ext,f.size,f.mtime FROM files f LEFT JOIN ocr_index o ON o.file_id=f.id' + where +
            ' AND (o.file_id IS NULL OR o.path!=f.path OR o.mtime!=f.mtime OR o.size!=f.size' +
            (" OR o.state='error'" if retry else '') + ') ORDER BY f.ts DESC', args)
        errors = recognized = 0
        for n, row in enumerate(rows):
            task.progress(done=n, total=len(rows), stage='Reading text in images', message=f'{n:,} of {len(rows):,} images and PDFs checked')
            result = {'text': '', 'state': 'unsupported', 'pages': 0}
            try:
                if row['ext'] in DECODABLE or row['ext'] == 'pdf':
                    path = fileops.safe_path(row['path'])
                    before = os.stat(path)
                    if before.st_size != row['size'] or abs(before.st_mtime - row['mtime']) > .001:
                        continue
                    if worker is None:
                        worker = Worker()
                    result = worker.extract(path, row['ext'], task)
                    after = os.stat(path)
                    if (before.st_size, before.st_mtime) != (after.st_size, after.st_mtime):
                        continue
            except jobs.Cancelled:
                raise
            except Exception:
                result = {'text': '', 'state': 'error', 'pages': 0}
                if worker:
                    worker.close(); worker = None
            task.progress()
            text = str(result.get('text', ''))[:100_000]
            with db.tx() as c:
                current = c.execute('SELECT path,mtime,size FROM files WHERE id=?', (row['id'],)).fetchone()
                if not current or tuple(current) != (row['path'], row['mtime'], row['size']):
                    continue
                c.execute('DELETE FROM ocr_text WHERE rowid=?', (row['id'],))
                if text.strip():
                    c.execute('INSERT INTO ocr_text(rowid,body) VALUES(?,?)', (row['id'], text))
                    recognized += 1
                c.execute('INSERT OR REPLACE INTO ocr_index VALUES(?,?,?,?,?,?,?)', (row['id'],row['path'],row['mtime'],row['size'],result['state'],result['pages'],time.time()))
            errors += result['state'] == 'error'
            if worker and (n + 1) % 200 == 0:
                worker.close(); worker = None
        task.progress(done=len(rows), total=len(rows), stage='Ready', message=f'{recognized:,} files with recognized text · {errors:,} unreadable')
        return {'recognized': recognized, 'errors': errors}
    finally:
        if worker:
            worker.close()
        scope.set_owners(None)


def status():
    where, args = scope.where('f.owner', "(f.cat='image' OR f.ext='pdf')")
    r = db.conn().execute("SELECT COUNT(*) total,SUM(o.file_id IS NOT NULL) checked,SUM(o.state='error') errors,"
        "SUM(o.state='partial') partial,SUM(o.file_id IN (SELECT rowid FROM ocr_text)) AS indexed "
        'FROM files f LEFT JOIN ocr_index o ON o.file_id=f.id AND o.path=f.path AND o.mtime=f.mtime AND o.size=f.size' + where, args).fetchone()
    return {**{k:r[k] or 0 for k in r.keys()}, 'local': True, 'task': next((t for t in jobs.history() if t['kind']=='ocr' and t['status'] in ('queued','running')),None)}
