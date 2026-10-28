"""Tiny background task runner with progress reporting.

Two queues: `indexer` (scan/hash/analyze, long running) and `ops` (deletes, moves), so file
operations never wait for a multi-hour index job.
"""
import itertools
import logging
import queue
import threading
import time
import traceback

log = logging.getLogger("supergallery")
_ids = itertools.count(1)
_history: list["Task"] = []
_lock = threading.Lock()


class Cancelled(Exception):
    pass


class Task:
    def __init__(self, kind: str, label: str, fn, *args, **kw):
        self.id = next(_ids)
        self.kind, self.label = kind, label
        self.fn, self.args, self.kw = fn, args, kw
        self.status = "queued"
        self.stage = ""
        self.total = 0
        self.done = 0
        self.message = ""
        self.result = None
        self.created = time.time()
        self.started = self.ended = None
        self.cancel_requested = False

    def progress(self, done=None, total=None, stage=None, message=None):
        if self.cancel_requested:
            raise Cancelled()
        if total is not None:
            self.total = getattr(self, '_batch_total', total)
        if done is not None:
            self.done = getattr(self, '_batch_offset', 0) + done
        if stage is not None:
            self.stage = stage
        if message is not None:
            self.message = message

    def step(self, n=1):
        self.done += n
        if self.cancel_requested:
            raise Cancelled()

    def to_dict(self):
        return {
            "id": self.id, "kind": self.kind, "label": self.label, "status": self.status,
            "stage": self.stage, "total": self.total, "done": self.done, "message": self.message,
            "result": self.result, "created": self.created, "started": self.started, "ended": self.ended,
        }


class Runner(threading.Thread):
    def __init__(self, name: str):
        super().__init__(name=name, daemon=True)
        self.q: "queue.Queue[Task]" = queue.Queue()
        self.current: Task | None = None

    def submit(self, task: Task) -> Task:
        with _lock:
            _history.append(task)
            completed=[t for t in _history if t.status not in ('queued','running')]
            stale=set(completed[:-40])
            _history[:]=[t for t in _history if t not in stale]
        self.q.put(task)
        return task

    def busy_with(self, kind: str) -> bool:
        if self.current and self.current.kind == kind:
            return True
        return any(t.kind == kind and t.status == "queued" for t in _history)

    def run(self):
        from .memory import lower_priority
        lower_priority()  # indexing yields the CPU to the web UI and other NAS apps
        while True:
            t = self.q.get()
            if t.cancel_requested:
                t.status = "cancelled"
                continue
            self.current = t
            t.status, t.started = "running", time.time()
            try:
                t.result = t.fn(t, *t.args, **t.kw)
                if isinstance(t.result, dict) and t.result.pop('_continue', False):
                    t.status, t.stage = 'queued', 'Waiting for the next batch'
                    t.message = f'{t.done:,} of {t.total:,} files checked; other indexing jobs can run'
                    self.q.put(t)
                else:
                    t.status = "done"
            except Cancelled:
                t.status = "cancelled"
            except Exception as e:  # noqa: BLE001 - surface any failure in the UI
                log.error("task %s failed: %s", t.label, traceback.format_exc())
                t.status, t.message = "error", str(e)
            finally:
                t.ended = None if t.status == 'queued' else time.time()
                self.current = None


def index_batch(task, sql, args):
    """Take a bounded turn from one stable snapshot, without retrying bad files forever."""
    from . import db
    if not getattr(task, 'batch_limit', None):
        return db.conn().execute(sql, args).fetchall()
    if not hasattr(task, '_pending_rows'):
        task._pending_rows = db.conn().execute(sql, args).fetchall()
        task._batch_total, task._batch_offset, task._batch_end = len(task._pending_rows), 0, 0
    task._batch_offset = task._batch_end
    task._batch_end = min(task._batch_total, task._batch_offset + task.batch_limit)
    return task._pending_rows[task._batch_offset:task._batch_end]


indexer = Runner("indexer")
ops = Runner("ops")
intelligence = Runner("intelligence")


def start():
    indexer.start()
    ops.start()
    intelligence.start()


def history():
    with _lock:
        return [t.to_dict() for t in reversed(_history)]


def get(task_id: int) -> Task | None:
    with _lock:
        return next((t for t in _history if t.id == task_id), None)
