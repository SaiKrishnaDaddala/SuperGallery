"""Text search finds Hindi and Telugu words and can rank the best matches first."""
from app import queries, search_index

from test_discovery import library  # noqa: F401  (shared fixture)


def ocr(c, fid, path, text):
    row = c.execute('SELECT * FROM files WHERE id=?', (fid,)).fetchone()
    c.execute('INSERT INTO ocr_index VALUES(?,?,?,?,?,?,0)', (fid, path.as_posix(), row['mtime'], row['size'], 'done', 1))
    c.execute('INSERT INTO ocr_text(rowid,body) VALUES(?,?)', (fid, text))


def test_indic_words_stay_whole():
    hindi, telugu = 'हिन्दी', 'తెలుగు'
    assert search_index.fts_terms(f'{hindi} {telugu}') == [hindi, telugu]
    assert search_index.fts_terms("don't \"stop\" a-b.c x2024") == ['don', 't', 'stop', 'a', 'b', 'c', 'x2024']


def test_hindi_and_telugu_text_in_photos_is_found(library):  # noqa: F811
    c, add, _ = library
    hindi, elephant, telugu = 'हिन्दी', 'हाथी', 'తెలుగు'
    a, pa = add('poster.png')
    b, pb = add('zoo.png')
    t, pt = add('board.png')
    ocr(c, a, pa, f'{hindi} दिवस')
    ocr(c, b, pb, f'{elephant} घर')
    ocr(c, t, pt, f'{telugu} భాష')
    found = lambda q: [x['id'] for x in queries.query({'text': q})['items']]
    assert found(hindi) == [a]
    assert found(elephant) == [b]
    assert found(telugu) == [t]


def test_best_match_puts_name_matches_first(library):  # noqa: F811
    c, add, _ = library
    inside, _ = add('scan_0001.png')
    c.execute('UPDATE files SET ts=ts+100 WHERE id=?', (inside,))
    ocr(c, inside, _, 'Invoice for March')
    named, _ = add('invoice-march.pdf', cat='document')
    by_date = [x['id'] for x in queries.query({'text': 'invoice'}, sort='ts', order='desc')['items']]
    best = [x['id'] for x in queries.query({'text': 'invoice'}, sort='relevance')['items']]
    assert by_date == [inside, named]
    assert best == [named, inside]
    assert queries.query({}, sort='relevance')['total'] == 2  # no words: falls back to the normal order
