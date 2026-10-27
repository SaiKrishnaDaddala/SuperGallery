"""Separate, time- and memory-limited document parser. Emits bounded plain text only."""
import json
import os
import sys
import zipfile
from xml.etree import ElementTree


def extract(path, ext):
    if os.path.getsize(path) > 10 * 1024 * 1024:
        raise ValueError("Document is too large")
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            return ""
        parts, size = [], 0
        for page in reader.pages[:80]:
            value = (page.extract_text() or "")[:100_000-size]
            parts.append(value)
            size += len(value)
            if size >= 100_000:
                break
        return "\n".join(parts)[:100_000]
    if ext == "docx":
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > 5 * 1024 * 1024:
                raise ValueError("Document text is too large")
            root = ElementTree.fromstring(z.read(info))
            return " ".join(n.text or "" for n in root.iter() if n.tag.endswith("}t"))[:100_000]
    with open(path, "rb") as f:
        data = f.read(400_000)
    return data.decode("utf-8-sig", errors="replace")[:100_000]


if __name__ == "__main__":
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    print(json.dumps({"text": extract(sys.argv[1], sys.argv[2])}, ensure_ascii=True))
