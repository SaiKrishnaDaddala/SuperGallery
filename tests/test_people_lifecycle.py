import numpy as np

from app import db, people


def setup_library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "index.db")
    db._local.__dict__.clear()
    db.init()
    people.init()
    c = db.conn()
    c.execute("INSERT INTO files(id,path,dir,name,ext,cat,size,mtime,ts,seen,owner) VALUES(1,'/lib/a.jpg','/lib','a.jpg','jpg','image',1,1,1,1,'alex')")
    c.execute("INSERT INTO face_index VALUES(1,'/lib/a.jpg',1,1,'done',1)")
    return c


def add_face(c, name):
    vector = np.ones(128, dtype="float32") / np.sqrt(128)
    pid = c.execute("INSERT INTO people(owner,prototype,created,name) VALUES('alex',?,1,?)", (vector.tobytes(), name)).lastrowid
    c.execute("INSERT INTO faces(file_id,person_id,embedding,crop,score) VALUES(1,?,?,x'00',1)", (pid, vector.tobytes()))
    return pid


def test_named_person_survives_deleting_their_last_photo(tmp_path, monkeypatch):
    c = setup_library(tmp_path, monkeypatch)
    pid = add_face(c, "Grandma")
    c.execute("DELETE FROM files WHERE id=1")
    assert c.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()[0] == "Grandma"
    assert c.execute("SELECT emptied FROM people WHERE id=?", (pid,)).fetchone()[0] is not None
    assert c.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    assert people.listing()["total"] == 0  # hidden while there are no photos


def test_unnamed_group_is_removed_with_its_last_photo(tmp_path, monkeypatch):
    c = setup_library(tmp_path, monkeypatch)
    pid = add_face(c, "")
    c.execute("DELETE FROM files WHERE id=1")
    assert c.execute("SELECT COUNT(*) FROM people WHERE id=?", (pid,)).fetchone()[0] == 0
