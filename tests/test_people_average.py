"""People are matched against the average of their faces, so slowly changing faces stay one person."""
import numpy as np

from app import db, jobs, people

from test_discovery import library  # noqa: F401  (shared fixture)


def unit(v):
    v = np.asarray(v, dtype='float32')
    return v / np.linalg.norm(v)


def drifting_faces(n):
    """Faces of one person whose look changes a little from photo to photo; the last is far from the first."""
    a, b = np.zeros(128, dtype='float32'), np.zeros(128, dtype='float32')
    a[0], b[1] = 1, 1
    return [unit(np.cos(t) * a + np.sin(t) * b) for t in np.linspace(0, 1.2, n)]


def test_slowly_changing_faces_stay_one_person(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    faces = drifting_faces(14)
    files = {}
    for i, f in enumerate(faces):
        fid, path = add(f'p{i:02}.jpg')
        c.execute('UPDATE files SET ts=? WHERE id=?', (1000 - i, fid))  # indexed oldest-last order: p00 first
        files[path.as_posix()] = f
    monkeypatch.setattr(people, 'engine', lambda: None)
    monkeypatch.setattr(people, 'detect', lambda path: [(files[path], b'jpg', .99)])
    monkeypatch.setattr(people, 'DECODABLE', {'jpg'})
    monkeypatch.setattr(jobs, 'index_batch', lambda task, sql, args: list(c.execute(sql, args)))

    class Task:
        def progress(self, *a, **kw):
            pass

    people.index(Task())
    groups = c.execute('SELECT COUNT(DISTINCT person_id) FROM faces').fetchone()[0]
    assert groups == 1
    # With only the first face as the reference, the later faces would have split off:
    assert float(faces[0] @ faces[-1]) < .55


def test_existing_groups_get_their_average_once(library):  # noqa: F811
    c, add, _ = library
    first, second = unit([1] + [0] * 127), unit([0, 1] + [0] * 126)
    fid, _ = add('x.jpg')
    pid = c.execute("INSERT INTO people(owner,prototype,created) VALUES('alice',?,1)", (first.tobytes(),)).lastrowid
    for f in (first, second):
        c.execute('INSERT INTO faces(file_id,person_id,embedding,crop,score) VALUES(?,?,?,?,1)', (fid, pid, f.tobytes(), b''))
    db.kv_set('people_prototypes', 'old')
    people.init()
    proto = np.frombuffer(c.execute('SELECT prototype FROM people WHERE id=?', (pid,)).fetchone()[0], dtype='float32')
    assert np.allclose(proto, unit(first + second), atol=1e-6)
    assert db.kv_get('people_prototypes') == people.PROTOTYPES
