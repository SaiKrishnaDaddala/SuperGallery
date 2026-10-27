"""Durable, serial local indexing. Completed per-file work survives every restart."""
import json
import threading
import time
from fastapi import HTTPException
from . import db, jobs, features

_submit_lock = threading.RLock()
LABELS = {'visual':'Understand photo contents','scenes':'Understand video scenes','ocr':'Read text in images',
          'faces':'Find people in photos','documents':'Make documents searchable'}


def init():
    db.conn().execute('CREATE TABLE IF NOT EXISTS intelligence_requests(id INTEGER PRIMARY KEY,kind TEXT,owners TEXT,state TEXT,created REAL,updated REAL)')


def _execute(task, request_id, kind, owners, retry):
    from . import people, search_index, visual_search, ocr_index
    db.conn().execute("UPDATE intelligence_requests SET state='running',updated=? WHERE id=?", (time.time(),request_id))
    state = 'done'
    try:
        if not features.enabled(features.KINDS[kind]):
            raise jobs.Cancelled()
        task.batch_limit = {'visual':100,'scenes':1,'ocr':25,'faces':100,'documents':50}[kind]
        if kind in ('visual','scenes'):
            result = visual_search.index(task,owners,retry,media='video' if kind=='scenes' else 'image')
        else:
            result = {'faces':people.index,'documents':search_index.index,'ocr':ocr_index.index}[kind](task,owners,retry)
        task.progress()
        totals=getattr(task,'_index_totals',{})
        for key,value in result.items():
            totals[key]=totals.get(key,0)+value
        task._index_totals=totals
        result=dict(totals)
        if task._batch_end < task._batch_total:
            state = 'queued'
            result['_continue'] = True
        else:
            del task._pending_rows
            task.progress(stage='Ready',message=f'{task.total:,} files checked; indexed results are ready')
        return result
    except jobs.Cancelled:
        state = 'paused'; raise
    except Exception:
        state = 'error'; raise
    finally:
        if not features.enabled(features.KINDS[kind]):
            state = 'paused'
        if state in ('paused','error') and hasattr(task,'_pending_rows'):
            del task._pending_rows
        db.conn().execute('UPDATE intelligence_requests SET state=?,updated=? WHERE id=?',(state,time.time(),request_id))


def submit(kind, owners=None, retry=False, request_id=None):
    with _submit_lock:
        if kind not in LABELS:
            raise HTTPException(400,'Choose a supported index.')
        features.require(features.KINDS[kind])
        if jobs.intelligence.busy_with(kind):
            raise HTTPException(409,'This indexing job is already queued or running.')
        if request_id is None:
            request_id = db.conn().execute("INSERT INTO intelligence_requests(kind,owners,state,created,updated) VALUES(?,?,'queued',?,?)",
                (kind,json.dumps(owners),time.time(),time.time())).lastrowid
        task = jobs.Task(kind,LABELS[kind],_execute,request_id,kind,owners,retry)
        task.persist_id = request_id
        return jobs.intelligence.submit(task)


def resume():
    rows = db.conn().execute("SELECT * FROM intelligence_requests WHERE state IN ('queued','running') ORDER BY id").fetchall()
    for row in rows:
        if features.enabled(features.KINDS[row['kind']]):
            submit(row['kind'],json.loads(row['owners']),request_id=row['id'])
        else:
            db.conn().execute("UPDATE intelligence_requests SET state='paused' WHERE id=?", (row['id'],))


def cancel(task):
    if getattr(task,'persist_id',None):
        db.conn().execute("UPDATE intelligence_requests SET state='paused',updated=? WHERE id=?",(time.time(),task.persist_id))


def refresh_enabled():
    """Revisit selected libraries after a scan only for indexing the user has enabled."""
    for row in db.conn().execute('SELECT kind,owners FROM intelligence_requests GROUP BY kind,owners').fetchall():
        # A paused job stays paused until the user explicitly resumes it.
        latest = db.conn().execute('SELECT state FROM intelligence_requests WHERE kind=? AND owners=? ORDER BY id DESC LIMIT 1',(row['kind'],row['owners'])).fetchone()
        if latest and latest[0]=='done' and features.enabled(features.KINDS[row['kind']]) and not jobs.intelligence.busy_with(row['kind']):
            submit(row['kind'],json.loads(row['owners']))
