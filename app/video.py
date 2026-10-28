"""Video metadata (duration, resolution) via PyAV in a helper process: header reads only, so it is fast even on large libraries."""
import logging
from concurrent.futures import ThreadPoolExecutor

from . import db, media

log = logging.getLogger("supergallery")


def probe(path: str):
    return media.probe(path)


def analyze_videos(task):
    if not media.AVAILABLE:
        return {"videos": 0}
    rows = db.conn().execute("SELECT id, path FROM files WHERE cat='video' AND analyzed=0").fetchall()
    task.progress(0, len(rows), stage="Reading video length & resolution")
    done = 0
    with ThreadPoolExecutor(4) as pool:
        for i in range(0, len(rows), 200):
            part = rows[i:i + 200]
            ok, bad = [], []
            for row, res in zip(part, pool.map(lambda r: probe(r[1]), part)):
                if res and (res[0] or res[2]):
                    ok.append((res[0], res[1], res[2], row[0]))
                else:
                    bad.append((row[0],))
            with db.tx() as t:
                t.executemany("UPDATE files SET analyzed=1, width=?, height=?, duration=? WHERE id=?", ok)
                t.executemany("UPDATE files SET analyzed=-1 WHERE id=?", bad)
            done += len(part)
            task.progress(done)
    log.info("video analysis finished: %s videos", done)
    return {"videos": done}
