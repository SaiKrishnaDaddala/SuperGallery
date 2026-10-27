"""Isolated, offline OCR worker; parent enforces a per-file time limit."""
import contextlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps


def engine():
    import rapidocr
    root = Path(rapidocr.__file__).parent / 'models'
    names = {'Det': 'PP-OCRv6_det_small.onnx', 'Rec': 'PP-OCRv6_rec_small.onnx', 'Cls': 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
    # Only explicit bundled paths are allowed; missing models never trigger downloads.
    for name in names.values():
        if not (root / name).is_file():
            raise RuntimeError('The bundled OCR model is missing.')
    return rapidocr.RapidOCR(params={**{key + '.model_path': str(root / name) for key, name in names.items()},
        'EngineConfig.onnxruntime.intra_op_num_threads': 2, 'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        'Global.log_level': 'error', 'Global.max_side_len': 2000, 'Global.text_score': .65})


def recognize(ocr, image):
    image.thumbnail((2000, 2000))
    result = ocr(image.convert('RGB'))
    return '\n'.join(result.txts or [])[:100_000]


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
