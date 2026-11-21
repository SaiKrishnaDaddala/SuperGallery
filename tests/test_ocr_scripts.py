"""Text recognition reads Hindi and Telugu, and older results can be read again once on request."""
from pathlib import Path

import pytest

from app import db, ocr_index, ocr_worker

from test_discovery import library  # noqa: F401  (shared fixture)

FONTS = Path('C:/Windows/Fonts')
HINDI, TELUGU = '\u092d\u093e\u0930\u0924 \u0938\u0930\u0915\u093e\u0930', '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41 \u0c2d\u0c3e\u0c37'


@pytest.mark.skipif(not all((ocr_worker.EXTRA / name).is_file() for name in ocr_worker.SCRIPTS.values())
                    or not (FONTS / 'Nirmala.ttc').is_file() or not (FONTS / 'gautami.ttf').is_file(),
                    reason='needs the Indian-script OCR models and Windows fonts to draw the sample')
def test_reads_hindi_telugu_and_english_together():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (900, 330), 'white')
    draw = ImageDraw.Draw(image)
    for y, font, text in ((30, 'gautami.ttf', TELUGU), (130, 'arial.ttf', 'Electricity Bill 2024'), (230, 'Nirmala.ttc', HINDI)):
        draw.text((40, y), text, fill='black', font=ImageFont.truetype(str(FONTS / font), 48))
    lines = ocr_worker.Reader()(image)
    assert TELUGU in lines and HINDI in lines and 'Electricity Bill 2024' in lines


def test_read_again_covers_files_read_by_the_previous_reader(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    seen = []

    class Worker:
        def extract(self, path, ext, task):
            seen.append(Path(path).name)
            return {'text': 'new reading', 'state': 'done', 'pages': 1}

        def close(self):
            pass

    monkeypatch.setattr(ocr_index, 'Worker', Worker)
    monkeypatch.setattr(ocr_index, 'DECODABLE', {'png'})
    monkeypatch.setattr(ocr_index.fileops, 'safe_path', lambda path: path)  # the fixture lives outside the library roots

    class Task:
        def progress(self, *a, **kw):
            pass

    import app.jobs as jobs
    monkeypatch.setattr(jobs, 'index_batch', lambda task, sql, args: list(c.execute(sql, args)))
    old, old_path = add('old.png')
    row = c.execute('SELECT * FROM files WHERE id=?', (old,)).fetchone()
    c.execute('INSERT INTO ocr_index VALUES(?,?,?,?,?,?,?)', (old, old_path.as_posix(), row['mtime'], row['size'], 'no_text', 1, 1.0))
    ocr_index.index(Task())                      # first run with the new reader: nothing to do, old result kept
    assert seen == [] and ocr_index.status()['read_before_update'] == 1
    ocr_index.index(Task(), retry='redo')        # asked once: the old file is read again
    assert seen == ['old.png'] and db.kv_get('ocr_redo') == '1'
    ocr_index.index(Task())                      # nothing older is left, so the request finishes
    assert seen == ['old.png'] and db.kv_get('ocr_redo') == '0'
    assert ocr_index.status()['read_before_update'] == 0
