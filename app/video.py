"""Video metadata (duration, resolution) via ffprobe — header reads only, so it is fast even on large libraries."""
import json
import logging
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from . import db
from .thumbs import FFMPEG

log = logging.getLogger("supergallery")
FFPROBE = shutil.which('ffprobe') or (str(Path(FFMPEG).with_name('ffprobe'+Path(FFMPEG).suffix)) if FFMPEG else None)


def probe(path: str):
    if not FFPROBE:
        return None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", path],
            capture_output=True, timeout=20, check=False).stdout
        d = json.loads(out or b"{}")
        st = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 0) or None
        return st.get("width"), st.get("height"), dur
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def analyze_videos(task):
    if not FFPROBE:
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
