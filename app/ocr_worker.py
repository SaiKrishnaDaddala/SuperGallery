"""Isolated, offline OCR worker; parent enforces a per-file time limit."""
import contextlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps


READER = 'ppocr6+indic-v1'  # changes when the text reader changes, so older results can be read again
EXTRA = Path(__file__).resolve().parent.parent / 'models' / 'ocr'
SCRIPTS = {'devanagari': 'devanagari_PP-OCRv5_rec_mobile.onnx', 'te': 'te_PP-OCRv5_rec_mobile.onnx'}
KEEP, SURE = .65, .90  # keep a line at this confidence; below SURE, also try the Indian-script readers
THREADS = {'EngineConfig.onnxruntime.intra_op_num_threads': 2, 'EngineConfig.onnxruntime.inter_op_num_threads': 1, 'Global.log_level': 'error'}


class Reader:
    """The main detector and reader, plus Hindi (Devanagari) and Telugu readers for the lines it is unsure about.

    The main models read Latin and Chinese; Indic lines come out as low-confidence gibberish or are dropped, so
    those lines alone are read again with the script-specific models and the most confident reading wins."""

    def __init__(self):
        import rapidocr
        root = Path(rapidocr.__file__).parent / 'models'
        names = {'Det': 'PP-OCRv6_det_small.onnx', 'Rec': 'PP-OCRv6_rec_small.onnx', 'Cls': 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
        # Only explicit bundled paths are allowed; missing models never trigger downloads.
        for name in names.values():
            if not (root / name).is_file():
                raise RuntimeError('The bundled OCR model is missing.')
        self.main = rapidocr.RapidOCR(params={**{key + '.model_path': str(root / name) for key, name in names.items()}, **THREADS,
            'Global.max_side_len': 2000, 'Global.text_score': .2})
        self.extra = []
        wanted = [s.strip() for s in os.environ.get('OCR_EXTRA_SCRIPTS', 'devanagari,te').split(',') if s.strip()]
        for script in wanted:
            path = EXTRA / SCRIPTS.get(script, '-')
            if path.is_file():
                lang = {'devanagari': rapidocr.LangRec.DEVANAGARI, 'te': rapidocr.LangRec.TE}[script]
                self.extra.append(rapidocr.RapidOCR(params={**THREADS, 'Rec.model_path': str(path), 'Rec.lang_type': lang,
                    'Rec.ocr_version': rapidocr.OCRVersion.PPOCRV5}))

    def __call__(self, image):
        image = image.convert('RGB')
        result = self.main(image)
        if result.boxes is None:
            return []
        lines = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            best = (float(score), text)
            if best[0] < SURE and self.extra:
                xs, ys = [p[0] for p in box], [p[1] for p in box]
                crop = image.crop((max(0, int(min(xs)) - 4), max(0, int(min(ys)) - 4), int(max(xs)) + 4, int(max(ys)) + 4))
                for reader in self.extra:
                    other = reader(crop, use_det=False, use_cls=False, use_rec=True)
                    if other.txts and other.txts[0].strip() and float(other.scores[0]) > best[0]:
                        best = (float(other.scores[0]), other.txts[0])
            if best[0] >= KEEP and best[1].strip():
                lines.append(best[1])
        return lines


def engine():
    return Reader()


def recognize(ocr, image):
    image.thumbnail((2000, 2000))
    return '\n'.join(ocr(image))[:100_000]


def extract(ocr, path, ext):
    if Path(path).stat().st_size > 50 * 1024 * 1024:
        return {'text': '', 'state': 'too_large', 'pages': 0}
    if ext != 'pdf':
        with Image.open(path) as image:
            image.draft('RGB', (2000, 2000))
            text = recognize(ocr, ImageOps.exif_transpose(image))
        return {'text': text, 'state': 'done' if text else 'no_text', 'pages': 1}
    import pypdfium2 as pdfium
    text, checked = [], 0
    with pdfium.PdfDocument(path) as document:
        count = len(document)
        for number in range(min(20, count)):
            page = document[number]
            try:
                tp=page.get_textpage()
                try:
                    existing = tp.get_text_range()
                finally:
                    tp.close()
                # Digital text remains searchable through the regular document index.
                if len(existing.strip()) < 30:
                    w, h = page.get_size()
                    scale = min(2.0, 2000 / max(w, h))
                    bitmap = page.render(scale=scale)
                    try:
                        text.append(recognize(ocr, bitmap.to_pil()))
                    finally:
                        bitmap.close()
                checked += 1
            finally:
                page.close()
        return {'text': '\n'.join(text)[:100_000], 'state': 'partial' if count > 20 else 'done', 'pages': checked}


def main():
    if sys.platform != 'win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3,) * 2)
    from . import analyzer  # registers HEIC support
    with contextlib.redirect_stdout(sys.stderr):
        ocr = engine()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                result = extract(ocr, request['path'], request['ext'])
        except Exception:
            result = {'text': '', 'state': 'error', 'pages': 0}
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
