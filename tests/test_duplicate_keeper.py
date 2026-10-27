import pytest

from app import queries


def copy(fid, path, mtime=100):
    return {"id": fid, "path": path, "name": path.rsplit("/", 1)[1], "mtime": mtime}


@pytest.fixture(autouse=True)
def roots(monkeypatch):
    monkeypatch.setattr(queries, "SCAN_ROOTS", ["/nas/Personal", "/nas/Volume1"])


@pytest.mark.parametrize("original, duplicate", [
    ("/nas/Personal/sai/Photos/Trips/Goa/IMG_1.jpg", "/nas/Personal/sai/Backups/Phone backup 2024/IMG_1.jpg"),
    ("/nas/Personal/sai/Photos/IMG_1.jpg", "/nas/Personal/sai/MobileBackup/Nothing A142/Download/IMG_1.jpg"),
    ("/nas/Personal/sai/Camera Roll/2024/IMG_1.jpg", "/nas/Personal/sai/Downloads/IMG_1.jpg"),
    ("/nas/Personal/sai/DCIM/Camera/IMG_1.jpg", "/nas/Personal/sai/WhatsApp/Media/WhatsApp Images/IMG_1.jpg"),
    ("/nas/Personal/sai/Pictures/IMG_1.jpg", "/nas/Personal/sai/Pictures/.thumbnails/IMG_1.jpg"),
])
def test_recommended_keeps_the_original_even_when_the_copy_looks_older(original, duplicate):
    files = [copy(2, original, mtime=200), copy(1, duplicate, mtime=100)]
    assert queries._pick_keeper(files, "recommended", None)["path"] == original
    assert queries._pick_keeper(list(reversed(files)), "recommended", None)["path"] == original


def test_folder_words_split_names_and_ignore_the_library_root():
    words = queries._folder_words("/nas/Volume1/Backups/MobileBackup/WhatsApp Images/x.jpg")
    assert {"backup", "mobile", "whatsapp", "image"} <= words
    assert "volume" not in words and "x" not in words


def test_word_matching_does_not_trip_on_lookalike_names():
    # 'Golden', 'Present' and 'Older' contain 'old'/'sent' but are not copy folders.
    files = [copy(1, "/nas/Personal/a/Golden Present Older/IMG.jpg", 100), copy(2, "/nas/Personal/a/Sent/IMG.jpg", 200)]
    assert queries._pick_keeper(files, "recommended", None)["id"] == 1


def test_older_copy_still_wins_when_folders_say_nothing():
    files = [copy(1, "/nas/Personal/a/Misc/IMG.jpg", 300), copy(2, "/nas/Personal/a/Other/IMG.jpg", 100)]
    assert queries._pick_keeper(files, "recommended", None)["id"] == 2
