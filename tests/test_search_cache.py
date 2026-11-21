"""Photo meaning search keeps vectors in memory only while needed and always reflects the current library."""
import numpy as np

from app import scope, visual_search

from test_discovery import library, vector  # noqa: F401  (shared fixture and helper)


def setup(monkeypatch):
    target = np.zeros(512, dtype='float32')
    target[0] = 1
    monkeypatch.setattr(visual_search, 'text_embedding', lambda text: target)
    near = np.zeros(512, dtype='float32')
    near[0], near[1] = .99, .141
    return target, near


def names(result):
    return [x['name'] for x in result['items']]


def test_results_follow_new_and_deleted_photos(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    target, near = setup(monkeypatch)
    a, _ = add('a.jpg')
    vector(c, a, target)
    assert names(visual_search.search('x')) == ['a.jpg']
    b, _ = add('b.jpg')
    vector(c, b, near)
    assert names(visual_search.search('x')) == ['a.jpg', 'b.jpg']
    c.execute('DELETE FROM files WHERE id=?', (a,))
    assert names(visual_search.search('x')) == ['b.jpg']


def test_selected_users_still_apply_with_the_cache(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    target, _ = setup(monkeypatch)
    vector(c, add('mine.jpg', owner='alice')[0], target)
    vector(c, add('theirs.jpg', owner='bob')[0], target)
    visual_search.search('x')
    scope.set_owners(['bob'])
    assert names(visual_search.search('x')) == ['theirs.jpg']


def test_idle_release_frees_the_vectors(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    target, _ = setup(monkeypatch)
    vector(c, add('a.jpg')[0], target)
    visual_search.search('x')
    assert visual_search._vectors
    monkeypatch.setattr(visual_search, '_last_used', 0.0)
    assert visual_search.release_idle(1)
    assert not visual_search._vectors
    assert names(visual_search.search('x')) == ['a.jpg']
