"""The recycle bin follows the selected users: listing, counts, restore and empty."""
import pytest
from fastapi import HTTPException

from app import db, fileops, main, scope


@pytest.fixture()
def bin_library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "index.db")
    monkeypatch.setattr(scope, "USERS_ROOT", "/nas/Personal")
    db._local.__dict__.clear()
    db.init()
    c = db.conn()
    rows = [("/nas/Personal/alex/a.jpg", "alex"), ("/nas/Personal/alex/b.jpg", "alex"), ("/nas/Personal/sam/c.jpg", "sam"), ("/nas/Shared/d.jpg", "shared")]
    for i, (path, owner) in enumerate(rows, 1):
        real = tmp_path / f"bin{i}.jpg"
        real.write_bytes(b"x")
        c.execute("INSERT INTO trash(id,orig_path,trash_path,size,is_dir,deleted_at,reason,owner) VALUES(?,?,?,1,0,1,'manual',?)", (i, path, str(real), owner))
    yield c
    scope.set_owners(None)


@pytest.fixture()
def ops(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "submit_op", lambda label, fn, *a, **kw: calls.append((fn, a[0])) or {"task": 1})
    return calls


def test_listing_and_search_stay_inside_the_selected_users(bin_library):
    assert main.trash()["total"] == 4
    scope.set_owners(["sam"])
    assert [t["orig_path"] for t in main.trash()["items"]] == ["/nas/Personal/sam/c.jpg"]
    assert main.trash(q="a.jpg")["total"] == 0
    scope.set_owners(["alex"])
    assert main.trash(q="A.JPG")["total"] == 1
    scope.set_owners(["alex", "shared"])
    assert main.trash()["total"] == 3


def test_empty_and_restore_all_only_touch_the_selected_users(bin_library, ops):
    scope.set_owners(["alex"])
    main.trash_empty({})
    main.trash_restore({})
    assert ops == [(fileops.empty_trash, [1, 2]), (fileops.restore, [1, 2])]


def test_picked_items_of_another_user_are_ignored(bin_library, ops):
    scope.set_owners(["alex"])
    main.trash_empty({"ids": [1, 3]})
    main.trash_restore({"ids": [3]})
    assert ops == [(fileops.empty_trash, [1]), (fileops.restore, [])]


def test_no_selection_still_reaches_everything(bin_library, ops):
    main.trash_empty({})
    assert sorted(ops[0][1]) == [1, 2, 3, 4]


def test_empty_list_erases_nothing(bin_library):
    class Task:
        cancelled = False

        def progress(self, *a, **kw):
            pass

        def check(self):
            pass

    fileops.empty_trash(Task(), [])
    assert bin_library.execute("SELECT COUNT(*) FROM trash").fetchone()[0] == 4


def test_older_items_get_an_owner_on_start(bin_library):
    bin_library.execute("UPDATE trash SET owner=NULL WHERE id=3")
    db.init()
    assert bin_library.execute("SELECT owner FROM trash WHERE id=3").fetchone()[0] == "sam"


def test_preview_serves_the_deleted_file_under_its_own_name(bin_library):
    r = main.trash_raw(3)
    assert r.path.endswith("bin3.jpg") and 'filename="c.jpg"' in r.headers["content-disposition"]
    assert r.headers["content-disposition"].startswith("inline")
    assert main.trash_raw(3, download=True).headers["content-disposition"].startswith("attachment")
    with pytest.raises(HTTPException):
        main.trash_raw(99)
