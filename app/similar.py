"""Groups visually similar photos (resized copies, re-saves, edits, burst shots).

Each photo carries two 64-bit difference hashes. Two photos are "similar" when the total Hamming
distance of both hashes is <= threshold (out of 128) and their aspect ratios match. Comparisons are
vectorised in tiles with numpy, so ~100k photos take well under a minute on a NAS CPU.
"""
import time

import numpy as np

from . import db

DEFAULT_THRESHOLD = 10
ROW_TILE = 256
COL_TILE = 16384


def compute(task, threshold: int = DEFAULT_THRESHOLD):
    c = db.conn()
    task.progress(0, 0, stage="Finding similar photos")
    rows = c.execute("""SELECT id, ha, hb, width, height FROM files
                        WHERE cat='image' AND analyzed=1 AND ha IS NOT NULL AND width>0 AND height>0""").fetchall()
    # Solid-colour images all hash to ~0 and would form one giant bogus group; skip them.
    rows = [r for r in rows if not (r[1] in (0, -1) and r[2] in (0, -1))]
    n = len(rows)
    ids = np.array([r[0] for r in rows], dtype=np.int64)
    A = np.array([r[1] for r in rows], dtype=np.int64).view(np.uint64)
    B = np.array([r[2] for r in rows], dtype=np.int64).view(np.uint64)
    ar = np.array([max(r[3], r[4]) / min(r[3], r[4]) for r in rows], dtype=np.float32)
    portrait = np.array([r[4] > r[3] for r in rows], dtype=bool)

    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    task.progress(0, n)
    for s in range(0, n, ROW_TILE):
        e = min(s + ROW_TILE, n)
        a, b, r_ar, r_po = A[s:e, None], B[s:e, None], ar[s:e, None], portrait[s:e, None]
        for cs in range(s, n, COL_TILE):
            ce = min(cs + COL_TILE, n)
            d = np.bitwise_count(a ^ A[None, cs:ce]) + np.bitwise_count(b ^ B[None, cs:ce])
            m = d <= threshold
            m &= np.abs(r_ar - ar[None, cs:ce]) <= 0.06 * r_ar
            m &= r_po == portrait[None, cs:ce]
            ii, jj = np.nonzero(m)
            for i, j in zip(ii + s, jj + cs):
                if i < j:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[rj] = ri
        task.progress(e)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(int(ids[i]))
    out = []
    gid = 0
    for members in groups.values():
        if len(members) > 1:
            gid += 1
            out.extend((gid, m) for m in members)
    with db.tx() as t:
        t.execute("DELETE FROM sim_groups")
        t.executemany("INSERT INTO sim_groups(gid, file_id) VALUES(?,?)", out)
    db.kv_set("similar_threshold", threshold)
    db.kv_set("similar_at", time.time())
    return {"groups": gid, "photos": len(out)}
