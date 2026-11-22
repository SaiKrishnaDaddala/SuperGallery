"""Things in photos: tag every indexed photo against a fixed list of everyday subjects, on the NAS.

Reuses the CLIP vectors that photo search already stores, so tagging costs one matrix product per photo and no
extra image decoding. Each label is described by a few prompt variants (averaged); a photo gets a tag when that
label clearly stands out among all labels (zero-shot softmax), so photos with no clear subject get no tags.
"""
import hashlib
import json
import time

import numpy as np
from fastapi import HTTPException

from . import db, features, jobs, scope

# (shown label, phrase used in the prompt). Order only affects ties.
LABELS = [
    ("people", "a group of people"), ("selfie", "a selfie"), ("baby", "a baby"), ("child", "a child"),
    ("wedding", "a wedding"), ("party", "a party"), ("birthday", "a birthday cake with candles"), ("festival", "a festival celebration"),
    ("fireworks", "fireworks"), ("concert", "a concert on stage"), ("dance", "people dancing"), ("prayer", "people praying"), ("event", "indian politicians at a public event"),
    ("portrait", "a portrait of a person"), ("_namaste", "a person greeting with folded hands"), ("_men", "men in white shirts standing together"),
    ("dog", "a dog"), ("cat", "a cat"), ("bird", "a bird"), ("cow", "a cow"), ("horse", "a horse"), ("elephant", "an elephant"),
    ("monkey", "a monkey"), ("fish", "fish"), ("butterfly", "a butterfly"), ("insect", "an insect"),
    ("flower", "flowers"), ("tree", "trees"), ("plant", "a potted plant"), ("garden", "a garden"),
    ("mountain", "mountains"), ("beach", "a beach"), ("sea", "the sea"), ("river", "a river"), ("lake", "a lake"),
    ("waterfall", "a waterfall"), ("sky", "the sky with clouds"), ("sunset", "a sunset"), ("night", "a night scene"),
    ("snow", "snow"), ("rain", "rain"), ("desert", "a desert"), ("forest", "a forest"), ("field", "a green field"),
    ("moon", "the moon"), ("stars", "stars in the night sky"),
    ("city", "a city skyline"), ("street", "a street"), ("building", "a building"), ("house", "a house"),
    ("temple", "a hindu temple building"), ("church", "a church"), ("mosque", "a mosque"), ("monument", "a historic monument"),
    ("bridge", "a bridge"), ("road", "a road"), ("park", "a park"), ("market", "a market"), ("shop", "a shop"),
    ("restaurant", "a restaurant"), ("hotel room", "a hotel room"), ("bedroom", "a bedroom"), ("living room", "a living room"),
    ("kitchen", "a kitchen"), ("office", "an office"), ("classroom", "a classroom"), ("hospital", "a hospital"),
    ("swimming pool", "a swimming pool"), ("stadium", "a stadium"),
    ("car", "a car"), ("motorcycle", "a motorcycle"), ("bicycle", "a bicycle"), ("bus", "a bus"), ("truck", "a truck"),
    ("train", "a train"), ("airplane", "an airplane"), ("boat", "a boat"), ("auto rickshaw", "an auto rickshaw"),
    ("rocket", "a rocket"),
    ("food", "a plate of food"), ("dosa", "a dosa"), ("rice", "a rice dish"), ("curry", "curry"), ("bread", "bread"),
    ("cake", "a cake"), ("sweets", "indian sweets"), ("fruit", "fruit"), ("vegetables", "vegetables"), ("pizza", "pizza"),
    ("ice cream", "ice cream"), ("coffee", "a cup of coffee"), ("tea", "a cup of tea"), ("drink", "a drink in a glass"),
    ("document", "a printed document"), ("receipt", "a shopping receipt"), ("invoice", "an invoice"), ("id card", "an id card or membership card"),
    ("certificate", "a certificate with a seal and signature"), ("handwriting", "handwritten notes"), ("book", "a book"), ("newspaper", "a newspaper"),
    ("whiteboard", "a whiteboard"), ("screenshot", "a screenshot of a phone screen"), ("chart", "a chart"), ("map", "a map"),
    ("poster", "a poster"), ("greeting", "a greeting card"), ("advertisement", "an advertisement"),
    ("email", "an email"), ("spreadsheet", "a spreadsheet"), ("menu", "a restaurant menu"), ("ticket", "a ticket"), ("qr code", "a qr code"),
    ("computer", "a computer"), ("laptop", "a laptop"), ("phone", "a mobile phone"), ("television", "a television"),
    ("camera", "a camera"), ("toy", "toys"), ("clothes", "clothes"), ("shoes", "shoes"), ("jewellery", "jewellery"),
    ("watch", "a wrist watch"), ("glasses", "eyeglasses"), ("painting", "a painting"), ("drawing", "a drawing"),
    ("statue", "a statue"), ("god", "a statue of a hindu deity decorated with flowers"), ("pooja", "a home pooja shelf with idols and lamps"), ("_lights", "candles and fairy lights at night"), ("coins", "coins"), ("money", "money notes"), ("medicine", "medicine"),
    ("cricket", "people playing cricket"), ("football", "people playing football"), ("gym", "a gym"), ("yoga", "yoga"),
    ("space", "outer space"), ("astronaut", "an astronaut"), ("text", "text"), ("logo", "a logo"),
    # Catch-alls that are never shown: they take the probability of photos with no clear subject.
    ("_abstract", "an abstract colourful pattern"), ("_texture", "a close-up texture"), ("_blurry", "a blurry out of focus photo"),
    ("_dark", "a very dark photo"), ("_plain", "a plain background"),
]
TEMPLATES = ["a photo of {}.", "a picture of {}.", "a close-up photo of {}."]
VERSION = hashlib.sha256(json.dumps([LABELS, TEMPLATES]).encode()).hexdigest()[:12]
TOP = 3          # at most this many tags per photo
MIN_PROB = 0.35  # a label must take this share of the zero-shot probability (noise images peak around 0.33)
SCALE = 100.0    # CLIP's logit scale

SCHEMA = """
CREATE TABLE IF NOT EXISTS photo_tags(file_id INTEGER NOT NULL, label TEXT NOT NULL, score REAL NOT NULL, PRIMARY KEY(file_id, label));
CREATE INDEX IF NOT EXISTS ix_photo_tags_label ON photo_tags(label, score);
CREATE TABLE IF NOT EXISTS tag_state(file_id INTEGER PRIMARY KEY, version TEXT NOT NULL, vector_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tag_labels(version TEXT NOT NULL, label TEXT NOT NULL, embedding BLOB NOT NULL, PRIMARY KEY(version, label));
CREATE TRIGGER IF NOT EXISTS remove_deleted_tags AFTER DELETE ON files BEGIN
 DELETE FROM photo_tags WHERE file_id=OLD.id;
 DELETE FROM tag_state WHERE file_id=OLD.id;
END;
"""


def init():
    db.conn().executescript(SCHEMA)


def label_matrix() -> np.ndarray:
    """Normalised text vectors for every label, computed once per label-list version and kept in the database."""
    from . import visual_search
    c = db.conn()
    rows = {r[0]: np.frombuffer(r[1], dtype='<f4') for r in c.execute('SELECT label, embedding FROM tag_labels WHERE version=?', (VERSION,))}
    if len(rows) != len(LABELS):
        rows = {}
        for label, phrase in LABELS:
            v = np.mean([visual_search.encode_text(t.format(phrase)) for t in TEMPLATES], axis=0)
            rows[label] = (v / np.linalg.norm(v)).astype('<f4')
        with db.tx() as t:
            t.execute('DELETE FROM tag_labels')
            t.executemany('INSERT INTO tag_labels VALUES(?,?,?)', [(VERSION, k, v.tobytes()) for k, v in rows.items()])
    return np.stack([rows[label] for label, _ in LABELS])


def pick(scores: np.ndarray) -> list[list[tuple[int, float]]]:
    """For each row of label similarities, the labels that clearly stand out: [(label index, probability)]."""
    z = SCALE * (scores - scores.max(axis=1, keepdims=True))
    p = np.exp(z)
    p /= p.sum(axis=1, keepdims=True)
    order = np.argsort(-p, axis=1)[:, :TOP]
    return [[(int(i), float(p[r, i])) for i in order[r] if p[r, i] >= MIN_PROB and not LABELS[i][0].startswith('_')] for r in range(len(p))]


def update(task=None) -> dict:
    """Tag photos whose vectors are new or changed since they were last tagged. Cheap: no image decoding."""
    from .visual_search import MODEL
    c = db.conn()
    todo = c.execute(
        "SELECT v.id, v.file_id, v.embedding FROM visual_vectors v JOIN visual_index i ON i.file_id=v.file_id "
        "JOIN files f ON f.id=i.file_id AND f.path=i.path AND f.mtime=i.mtime AND f.size=i.size "
        "LEFT JOIN tag_state s ON s.file_id=v.file_id "
        "WHERE f.cat='image' AND i.model=? AND i.state='done' AND (s.file_id IS NULL OR s.version!=? OR s.vector_id!=v.id)",
        (MODEL, VERSION)).fetchall()
    if not todo:
        db.kv_set('tags_version', VERSION)
        return {'tagged': 0}
    labels = label_matrix()
    names = [label for label, _ in LABELS]
    tagged = 0
    for start in range(0, len(todo), 2048):
        chunk = [r for r in todo[start:start + 2048] if len(r[2]) == 1024]
        if task:
            task.progress(done=start, total=len(todo), stage='Recognising things in photos', message=f'{start:,} of {len(todo):,} photos')
        if not chunk:
            continue
        vectors = np.stack([np.frombuffer(r[2], dtype='<f2') for r in chunk]).astype('float32')
        picks = pick(vectors @ labels.T)
        with db.tx() as t:
            for row, chosen in zip(chunk, picks):
                t.execute('DELETE FROM photo_tags WHERE file_id=?', (row[1],))
                t.executemany('INSERT INTO photo_tags VALUES(?,?,?)', [(row[1], names[i], round(prob, 4)) for i, prob in chosen])
                t.execute('INSERT OR REPLACE INTO tag_state VALUES(?,?,?)', (row[1], VERSION, row[0]))
                tagged += bool(chosen)
    db.kv_set('tags_version', VERSION)
    return {'tagged': tagged, 'checked': len(todo)}


def listing(limit: int = 60, min_count: int = 1) -> dict:
    """Labels in the current scope with their photo counts and a cover photo (the most confident one)."""
    if not features.enabled('photo_search'):
        return {'tags': []}
    where, args = scope.where('f.owner')
    rows = db.conn().execute(
        "SELECT t.label, COUNT(*) n, (SELECT t2.file_id FROM photo_tags t2 JOIN files f2 ON f2.id=t2.file_id "
        "WHERE t2.label=t.label" + (" AND " + scope.cond('f2.owner')[0] if scope.owners() else "") + " ORDER BY t2.score DESC LIMIT 1) cover "
        "FROM photo_tags t JOIN files f ON f.id=t.file_id" + where + " GROUP BY t.label HAVING n>=? ORDER BY n DESC, t.label LIMIT ?",
        (scope.cond('f2.owner')[1] if scope.owners() else []) + args + [min_count, limit]).fetchall()
    return {'tags': [{'label': r[0], 'count': r[1], 'cover': r[2]} for r in rows]}


def labels_for(file_id: int) -> list[dict]:
    return [{'label': r[0], 'score': r[1]} for r in db.conn().execute(
        'SELECT label, score FROM photo_tags WHERE file_id=? ORDER BY score DESC', (file_id,))]


def known(label: str) -> str:
    label = str(label).strip().lower()
    if label.startswith('_') or label not in {name for name, _ in LABELS}:
        raise HTTPException(404, 'Unknown thing')
    return label
