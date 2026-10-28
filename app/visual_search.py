"""Local CLIP retrieval over photos and bounded video samples. No network calls."""
import hashlib
import heapq
import io
import math
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from fastapi import HTTPException
from . import db, fileops, jobs, queries, scope, video
from .config import DECODABLE
from . import media as media_helper

VIDEO_AVAILABLE = media_helper.AVAILABLE

MODEL = 'clip-b32-q8-v1'
MODELS = Path(__file__).resolve().parent.parent / 'models/semantic'
HASHES = {
    'text_model_quantized.onnx': '73baab855d406190da9faa498cfedf65f15cf309f4cc7385b7b032e6d08e5c3a',
    'vision_model_quantized.onnx': '583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299',
    'tokenizer.json': 'f7f3b7af117d467b58374797691a6438d3e6b9e9cef800dfd5dced7f697a90cd',
}
_lock = threading.RLock()
_sessions = {}
_tokenizer = None
_last_used = 0.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_index(file_id INTEGER PRIMARY KEY, path TEXT NOT NULL,
 mtime REAL NOT NULL,size INTEGER NOT NULL,model TEXT NOT NULL,state TEXT NOT NULL,
 samples INTEGER NOT NULL, interval_seconds REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS visual_vectors(id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL,
 seconds REAL NOT NULL,embedding BLOB NOT NULL,preview BLOB);
CREATE INDEX IF NOT EXISTS ix_visual_file ON visual_vectors(file_id);
CREATE TRIGGER IF NOT EXISTS remove_deleted_visual AFTER DELETE ON files BEGIN
 DELETE FROM visual_vectors WHERE file_id=OLD.id;
 DELETE FROM visual_index WHERE file_id=OLD.id;
END;
"""


def init():
    db.conn().executescript(SCHEMA)


def session(kind):
    global _last_used
    with _lock:
        _last_used = time.monotonic()
        if kind not in _sessions:
            import onnxruntime as ort
            name = kind + '_model_quantized.onnx'
            path = MODELS / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[name]:
                raise RuntimeError('The visual search model is missing or damaged. Reinstall the model bundle.')
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            options.add_session_config_entry('session.intra_op.allow_spinning', '0')
            _sessions[kind] = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
        return _sessions[kind]


def release_idle(seconds):
    """Drop the CLIP models and tokenizer after `seconds` without use; they reload on demand."""
    global _tokenizer
    with _lock:
        if (_sessions or _tokenizer is not None) and time.monotonic() - _last_used > seconds:
            _sessions.clear()
            _tokenizer = None
            return True
    return False


def normalize(vector):
    v = np.asarray(vector, dtype='float32').reshape(-1)
    norm = float(np.linalg.norm(v))
    if v.size != 512 or not np.isfinite(v).all() or norm < 1e-8:
        raise ValueError('Invalid visual embedding')
    return v / norm


def image_embedding(image):
    # Match CLIP's published RGB/bicubic/center-crop/normalization preprocessing.
    image = image.convert('RGB')
    w, h = image.size
    scale = 224 / min(w, h)
    resized = image.resize((max(224, int(w * scale)), max(224, int(h * scale))), Image.Resampling.BICUBIC)
    x, y = (resized.width - 224) // 2, (resized.height - 224) // 2
    array = np.asarray(resized.crop((x, y, x + 224, y + 224)), dtype='float32') / 255
    array = (array - np.array([.48145466, .4578275, .40821073], dtype='float32')) / np.array([.26862954, .26130258, .27577711], dtype='float32')
    with _lock:
        return normalize(session('vision').run(['image_embeds'], {'pixel_values': array.transpose(2, 0, 1)[None]})[0])


@lru_cache(maxsize=64)
def text_embedding(text):
    global _tokenizer
    with _lock:
        if _tokenizer is None:
            from tokenizers import Tokenizer
            path = MODELS / 'tokenizer.json'
            if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[path.name]:
                raise RuntimeError('The visual search tokenizer is damaged.')
            _tokenizer = Tokenizer.from_file(str(path))
            _tokenizer.no_truncation()
        # Never silently truncate a description to a different search.
        tokens = _tokenizer.encode('a photo of ' + text.strip()).ids
        if len(tokens) > 77:
            raise HTTPException(400, 'Use a shorter description, around 50 words or fewer.')
        result = session('text').run(['text_embeds'], {'input_ids': np.array([tokens], dtype='int64')})[0]
        return normalize(result)


def sample_times(duration):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Video duration is unavailable')
    interval = max(15.0, duration / 120)
    return [min(duration * .5, 1.0)] + [float(t) for t in np.arange(interval, duration, interval)][:119], interval


def video_frame(path, seconds):
    image = media_helper.frame(path, seconds, 640, timeout=25)
    if image is None:
        raise RuntimeError('No video frame at this time')
    return image


def index(task, owners=None, retry=False, media='image'):
    scope.set_owners(owners)
    try:
        session('vision')
        if media == 'video' and not VIDEO_AVAILABLE:
            raise RuntimeError('Video search needs the PyAV video library, which is missing from this installation.')
        where, args = scope.where('f.owner', 'f.cat=?', [media])
        rows = jobs.index_batch(task, 'SELECT f.id,f.path,f.mtime,f.size,f.ext,f.duration FROM files f LEFT JOIN visual_index v ON v.file_id=f.id' + where +
            " AND (v.file_id IS NULL OR v.path!=f.path OR v.mtime!=f.mtime OR v.size!=f.size OR v.model!=?" +
            (" OR v.state='error'" if retry else '') + ') ORDER BY f.ts DESC,f.id', args + [MODEL])
        errors = samples = 0
        for n, row in enumerate(rows):
            task.progress(done=n, total=len(rows), stage='Understanding videos' if media == 'video' else 'Understanding photos',
                message=f'{n:,} of {len(rows):,} {"videos" if media == "video" else "photos"} checked · {samples:,} views indexed')
            records, state, interval = [], 'done', 0
            try:
                path = fileops.safe_path(row['path'])
                stat = os.stat(path)
                if stat.st_size != row['size'] or abs(stat.st_mtime - row['mtime']) > .001:
                    continue
                if media == 'video':
                    metadata = video.probe(path) if not row['duration'] else None
                    times, interval = sample_times(float(row['duration'] or (metadata[2] if metadata else 0)))
                    for at in times:
                        task.progress(message=f'{n:,} of {len(rows):,} videos · sampling {int(at)} seconds')
                        frame = video_frame(path, at)
                        vector = image_embedding(frame)
                        frame.thumbnail((320, 320))
                        buffer = io.BytesIO(); frame.save(buffer, 'JPEG', quality=78)
                        records.append((row['id'], at, vector.astype('<f2').tobytes(), buffer.getvalue()))
                elif row['ext'] in DECODABLE:
                    with Image.open(path) as source:
                        source.draft('RGB', (1280, 1280))
                        image = ImageOps.exif_transpose(source).convert('RGB')
                        image.thumbnail((1600, 1600))
                    records.append((row['id'], 0, image_embedding(image).astype('<f2').tobytes(), None))
                else:
                    state = 'unsupported'
                stat_after = os.stat(path)
                if (stat.st_size, stat.st_mtime) != (stat_after.st_size, stat_after.st_mtime):
                    continue
            except jobs.Cancelled:
                raise
            except Exception:
                state, errors, records = 'error', errors + 1, []
            task.progress()
            with db.tx() as c:
                current = c.execute('SELECT path,mtime,size FROM files WHERE id=?', (row['id'],)).fetchone()
                if not current or tuple(current) != (row['path'], row['mtime'], row['size']):
                    continue
                c.execute('DELETE FROM visual_vectors WHERE file_id=?', (row['id'],))
                c.executemany('INSERT INTO visual_vectors(file_id,seconds,embedding,preview) VALUES(?,?,?,?)', records)
                c.execute('INSERT OR REPLACE INTO visual_index VALUES(?,?,?,?,?,?,?,?,?)',
                    (row['id'], row['path'], row['mtime'], row['size'], MODEL, state, len(records), interval, time.time()))
            samples += len(records)
        task.progress(done=len(rows), total=len(rows), stage='Ready', message=f'{samples:,} views searchable · {errors:,} unreadable files')
        return {'files': len(rows), 'samples': samples, 'errors': errors}
    finally:
        scope.set_owners(None)


def status(media='image'):
    where, args = scope.where('f.owner', 'f.cat=?', [media])
    r = db.conn().execute("SELECT COUNT(*) total,SUM(v.state='done') AS indexed,SUM(v.state IS NOT NULL) checked,"
        "SUM(v.state='error') errors,SUM(v.state='unsupported') unsupported,COALESCE(SUM(v.samples),0) samples "
        'FROM files f LEFT JOIN visual_index v ON v.file_id=f.id AND v.path=f.path AND v.mtime=f.mtime AND v.size=f.size AND v.model=?' + where,
        [MODEL] + args).fetchone()
    return {**{k: r[k] or 0 for k in r.keys()}, 'local': True, 'media': media,
        'task': next((t for t in jobs.history() if t['kind'] == ('scenes' if media == 'video' else 'visual') and t['status'] in ('queued', 'running')), None)}


def search(text, filters=None, media='image', limit=60, offset=0):
    query = str(text).strip()
    if not query or len(query) > 300:
        raise HTTPException(400, 'Describe the scene in 1–300 characters.')
    target = text_embedding(query)
    where, args = queries.build_where({**(filters or {}), 'cat': [media]})
    cursor = db.conn().execute('SELECT v.id,v.file_id,v.seconds,v.embedding FROM visual_vectors v JOIN visual_index i ON i.file_id=v.file_id '
        'JOIN (SELECT id,path,mtime,size FROM files' + where + ') f ON f.id=i.file_id AND f.path=i.path AND f.mtime=i.mtime AND f.size=i.size '
        "WHERE i.model=? AND i.state='done' ORDER BY v.id", args + [MODEL])
    # Stream bounded chunks rather than keeping the library's vectors in RAM.
    best = {}
    while batch := cursor.fetchmany(1024):
        valid = [r for r in batch if len(r['embedding']) == 1024]
        if not valid:
            continue
        matrix = np.stack([np.frombuffer(r['embedding'], dtype='<f2') for r in valid]).astype('float32')
        scores = matrix @ target
        for row, score in zip(valid, scores):
            score = float(score)
            if math.isfinite(score) and score >= .23 and (row['file_id'] not in best or score > best[row['file_id']][0]):
                best[row['file_id']] = (score, row['id'], row['seconds'])
    ranked = heapq.nlargest(240, best.items(), key=lambda pair: (pair[1][0], -pair[0]))
    # Similarity is a ranking signal, not a probability or verified description.
    if ranked:
        floor = max(.23, ranked[0][1][0] - .04)
        ranked = [pair for pair in ranked if pair[1][0] >= floor]
    items = []
    for fid, (score, scene_id, seconds) in ranked[offset:offset + limit]:
        # Recheck scope/freshness in case a file changed while ranking.
        rows = queries.query({**(filters or {}), 'ids': [fid], 'cat': [media]}, limit=1)['items']
        fresh = db.conn().execute('SELECT 1 FROM visual_index i JOIN files f ON f.id=i.file_id AND f.path=i.path AND f.mtime=i.mtime AND f.size=i.size WHERE f.id=? AND i.model=?', (fid, MODEL)).fetchone()
        if rows and fresh:
            items.append({**rows[0], 'similarity': round(score, 4), 'scene_id': scene_id if media == 'video' else None, 'start_seconds': seconds})
    return {'items': items, 'total': len(ranked), 'has_more': offset + limit < len(ranked), 'limit': 240,
        'status': status(media), 'description': query}


def frame(scene_id):
    where, args = scope.where('f.owner', 'v.id=? AND f.cat=\'video\'', [scene_id])
    r = db.conn().execute('SELECT v.preview FROM visual_vectors v JOIN visual_index i ON i.file_id=v.file_id '
        'JOIN files f ON f.id=i.file_id AND f.path=i.path AND f.mtime=i.mtime AND f.size=i.size' + where, args).fetchone()
    if not r or not r[0]:
        raise HTTPException(404, 'This video scene is no longer available.')
    return bytes(r[0])
