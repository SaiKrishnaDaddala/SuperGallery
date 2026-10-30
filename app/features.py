"""Persistent instance-wide optional capabilities, independent of authentication."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool
from . import db, jobs

VERSION = '2.5.0'
CATALOG = {
    'photo_search': ('Photo meaning', 'Find activities, objects and places with local visual search.'),
    'video_search': ('Video scenes', 'Search sampled video frames and jump to matching timestamps.'),
    'documents': ('Document text', 'Extract searchable text from digital documents.'),
    'ocr': ('Text recognition', 'Read printed text in screenshots, photos and scanned PDFs.'),
    'people': ('People', 'Group similar faces locally and add names yourself.'),
    'albums': ('Smart albums', 'Save searches that update as your library changes.'),
    'uploads': ('Uploads', 'Add files from your browser or phone to writable library folders.'),
    'cleanup': ('Duplicate and cleanup tools', 'Review exact duplicates, similar photos and cleanup suggestions.'),
    'automation': ('Cleanup automation', 'Run saved cleanup rules on their schedules. Requires cleanup tools.'),
}
KINDS = {'visual':'photo_search', 'scenes':'video_search', 'documents':'documents', 'ocr':'ocr', 'faces':'people', 'rule':'automation', 'similar':'cleanup'}
router = APIRouter(prefix='/api/features')


def settings():
    raw = json.loads(db.kv_get('features', '{}'))
    if not isinstance(raw, dict):
        raise RuntimeError('Feature settings are damaged. Restore your app-data backup.')
    # Existing installations retain all capabilities. Indexing remains opt-in.
    return {key: raw.get(key, True) is True for key in CATALOG}


def enabled(key):
    values = settings()
    return values[key] and (key != 'automation' or values['cleanup'])


def require(key):
    if not enabled(key):
        raise HTTPException(403, f'{CATALOG[key][0]} is turned off. Enable it in Settings → Features.')


def boundary(path):
    for prefixes, key in [
        (('/api/people', '/api/faces'), 'people'),
        (('/api/albums',), 'albums'),
        (('/api/uploads', '/api/upload'), 'uploads'),
        (('/api/ocr',), 'ocr'),
        (('/api/search/index', '/api/search/clear'), 'documents'),
        (('/api/rules',), 'automation'),
        (('/api/quickclean', '/api/dupfolders', '/api/duplicates', '/api/similar', '/api/cleanup', '/api/empty-folders', '/api/learned'), 'cleanup'),
    ]:
        if any(path == p or path.startswith(p + '/') for p in prefixes):
            require(key)


def describe():
    values = settings()
    return {'version': VERSION, 'values': values, 'catalog': [
        {'key': key, 'label': label, 'description': description, 'enabled': values[key],
         'effective': values[key] and (key != 'automation' or values['cleanup'])}
        for key, (label, description) in CATALOG.items()]}


class Changes(BaseModel):
    model_config = ConfigDict(extra='forbid')
    values: dict[str, StrictBool]


@router.get('')
def get_features():
    return describe()


@router.put('')
def update_features(body: Changes):
    if set(body.values) - CATALOG.keys():
        raise HTTPException(422, 'Unknown feature. Authentication and backups cannot be disabled here.')
    from . import intelligence_tasks, queries
    # Serialize with index submission so disabling cannot race a new queued job.
    with intelligence_tasks._submit_lock:
        values = {**settings(), **body.values}
        with db.tx():
            db.kv_set('features', json.dumps(values))
            for kind, key in KINDS.items():
                if not values[key] or (key == 'automation' and not values['cleanup']):
                    db.conn().execute("UPDATE intelligence_requests SET state='paused' WHERE kind=? AND state IN ('queued','running')", (kind,))
                    for record in jobs.history():
                        task = jobs.get(record['id'])
                        if task and task.kind == kind and task.status in ('queued', 'running'):
                            task.cancel_requested = True
        queries.invalidate()
    return describe()
