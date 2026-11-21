"""Places: where photos were taken, named from their GPS tags entirely on the NAS.

Reads only the EXIF GPS block (no pixel decoding) and names each location after the nearest town from a bundled
GeoNames list (towns of 5,000+ people, CC BY 4.0). No map service or network call is involved.
"""
import gzip
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from . import db, scope
from .config import ANALYZE_WORKERS

DATA = Path(__file__).resolve().parent / 'geo' / 'places.tsv.gz'
GPS_IFD = 0x8825
EXIF_EXTS = ('jpg', 'jpeg', 'heic', 'heif', 'tif', 'tiff', 'webp', 'png', 'dng')
FAR_KM = 60  # farther than this from any listed town: name only the region and country
_lock = threading.Lock()
_towns = None


def towns():
    """(names, unit vectors) for every listed town, loaded once."""
    global _towns
    with _lock:
        if _towns is None:
            names, xyz = [], []
            with gzip.open(DATA, 'rt', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    name, region, country, lat, lon = line.rstrip('\n').split('\t')
                    names.append((name, region, country))
                    xyz.append((float(lat), float(lon)))
            _towns = (names, unit(np.array(xyz, dtype=np.float64)).astype(np.float32))
        return _towns


def unit(latlon: np.ndarray) -> np.ndarray:
    lat, lon = np.radians(latlon[:, 0]), np.radians(latlon[:, 1])
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=1)


def name_places(coords: list[tuple[float, float]]) -> list[str]:
    """'Town|Region|Country' for each (lat, lon); just 'Region|Country' when no town is near."""
    if not coords:
        return []
    names, mat = towns()
    out = []
    pts = unit(np.array(coords, dtype=np.float64)).astype(np.float32)
    for start in range(0, len(pts), 64):
        sims = pts[start:start + 64] @ mat.T
        best = sims.argmax(axis=1)
        for k, i in enumerate(best):
            km = 6371 * float(np.arccos(np.clip(sims[k, i], -1, 1)))
            town, region, country = names[i]
            out.append(f'{town}|{region}|{country}' if km <= FAR_KM else f'|{region}|{country}')
    return out


def _ratio(v) -> float:
    try:
        return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)
    except (TypeError, ZeroDivisionError, ValueError):
        return float('nan')


def gps(path: str):
    """(lat, lon) from the photo's EXIF GPS tags, or None. Reads the header only."""
    try:
        with Image.open(path) as im:
            g = im.getexif().get_ifd(GPS_IFD)
    except Exception:  # noqa: BLE001 - unreadable or no EXIF
        return None
    if not g or 2 not in g or 4 not in g:
        return None
    try:
        lat = sum(_ratio(x) / 60 ** i for i, x in enumerate(g[2]))
        lon = sum(_ratio(x) / 60 ** i for i, x in enumerate(g[4]))
    except TypeError:
        return None
    if str(g.get(1, 'N')).upper().startswith('S'):
        lat = -lat
    if str(g.get(3, 'E')).upper().startswith('W'):
        lon = -lon
    if not (np.isfinite(lat) and np.isfinite(lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    return round(lat, 5), round(lon, 5)


def update(task=None) -> dict:
    """Read GPS for photos not checked yet and name their places."""
    c = db.conn()
    rows = c.execute(f"SELECT id, path FROM files WHERE cat='image' AND geo IS NULL AND ext IN ({','.join('?' * len(EXIF_EXTS))})", EXIF_EXTS).fetchall()
    if not rows:
        return {'places': 0}
    found = 0
    with ThreadPoolExecutor(max(1, ANALYZE_WORKERS)) as pool:
        for start in range(0, len(rows), 500):
            part = rows[start:start + 500]
            if task:
                task.progress(start, len(rows), stage='Finding where photos were taken')
            coords = list(pool.map(lambda r: gps(r[1]), part))
            located = [(r, xy) for r, xy in zip(part, coords) if xy]
            labels = name_places([xy for _, xy in located])
            with db.tx() as t:
                t.executemany('UPDATE files SET geo=-1 WHERE id=?', [(r[0],) for r, xy in zip(part, coords) if not xy])
                t.executemany('UPDATE files SET geo=1, lat=?, lon=?, place=? WHERE id=?',
                              [(xy[0], xy[1], label, r[0]) for (r, xy), label in zip(located, labels)])
            found += len(located)
    return {'places': found, 'checked': len(rows)}


def label(place: str) -> dict:
    town, region, country = (place.split('|') + ['', '', ''])[:3]
    return {'key': place, 'name': town or region or country, 'area': ', '.join(x for x in (region if town else '', country) if x)}


def listing(limit: int = 60) -> dict:
    """Places in the current scope, most photos first, each with its newest photo as cover."""
    where, args = scope.where(extra="place IS NOT NULL AND cat='image'")
    rows = db.conn().execute(f"SELECT place, COUNT(*) n, MAX(ts) newest FROM files{where} GROUP BY place ORDER BY n DESC, place LIMIT ?",
                             args + [limit]).fetchall()
    out = []
    for place, n, _ in rows:
        cw, cp = scope.where(extra="place=? AND cat='image'", params=[place])
        cover = db.conn().execute(f'SELECT id FROM files{cw} ORDER BY ts DESC LIMIT 1', cp).fetchone()
        out.append({**label(place), 'count': n, 'cover': cover[0] if cover else None})
    return {'places': out}
