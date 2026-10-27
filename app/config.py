"""Runtime configuration, read from environment variables."""
import os
from pathlib import Path


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def fwd(p: str) -> str:
    """Paths are handled with forward slashes everywhere (no-op on Linux; lets the app run on Windows for dev)."""
    return p.replace("\\", "/") if os.sep == "\\" else p


# Folders inside the container that get indexed. Mount your NAS volume(s) here.
SCAN_ROOTS = [fwd(os.path.realpath(p)) for p in _list("SCAN_ROOTS", "/nas")]

# Folder whose sub-folders are per-user homes (UGOS personal folders). Files elsewhere count as "shared".
_users_root = os.environ.get("USERS_ROOT", "/nas/Personal")
USERS_ROOT = fwd(os.path.realpath(_users_root)) if _users_root else ""

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
DB_PATH = CONFIG_DIR / "index.db"
THUMB_DIR = CONFIG_DIR / "thumbs"
WEB_DIR = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent / "web"))

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

TRASH_NAME = ".supergallery_trash"
TRASH_RETENTION_DAYS = int(os.environ.get("TRASH_RETENTION_DAYS", "30"))
SCAN_INTERVAL_HOURS = float(os.environ.get("SCAN_INTERVAL_HOURS", "24"))
HASH_WORKERS = int(os.environ.get("HASH_WORKERS", "4"))
ANALYZE_WORKERS = int(os.environ.get("ANALYZE_WORKERS", str(max(2, (os.cpu_count() or 4) - 1))))
MIN_DUP_SIZE = int(os.environ.get("MIN_DUP_SIZE", "1"))

# Folder names that are never scanned or touched (NAS system / recycle / app data).
EXCLUDE_NAMES = set(_list(
    "EXCLUDE_NAMES",
    "@eaDir,#recycle,#snapshot,.@__thumb,@Recycle,@Recently-Snapshot,.Trash-1000,lost+found,"
    "$RECYCLE.BIN,System Volume Information,.ugreen_nas,.fscrypt,docker,@docker,@appstore," + TRASH_NAME,
))
EXCLUDE_PREFIXES = tuple(_list("EXCLUDE_PREFIXES", "@,.@,.sg-upload-"))

CATEGORIES = {
    "image": "jpg jpeg jfif png gif bmp webp heic heif avif tif tiff ico svg psd raw cr2 cr3 nef arw dng orf rw2 raf srw pef",
    "video": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts mts m2ts vob ogv rm rmvb divx",
    "audio": "mp3 flac wav aac ogg m4a wma opus aiff aif ape alac mid midi amr",
    "document": "pdf doc docx xls xlsx ppt pptx odt ods odp txt rtf md csv epub mobi azw3 pages numbers key tex",
    "archive": "zip rar 7z tar gz tgz bz2 xz iso img dmg cab lz zst",
    "code": "py js ts jsx tsx html htm css json xml yml yaml sh c cpp h hpp java go rs php rb sql ipynb kt swift",
    "app": "exe msi apk deb rpm pkg appimage bat cmd",
}
EXT_CAT = {e: c for c, exts in CATEGORIES.items() for e in exts.split()}

# Images Pillow can decode for hashing / thumbnails.
DECODABLE = set("jpg jpeg jfif png gif bmp webp tif tiff ico heic heif avif".split())
VIDEO_THUMB = set(CATEGORIES["video"].split())

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)
