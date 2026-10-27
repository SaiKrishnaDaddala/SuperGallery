import os
import sqlite3
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fastapi import HTTPException

os.environ.setdefault("CONFIG_DIR", str(Path(__file__).parent.parent / ".work/unit-config"))
from app import db, people, scope, queries, search_index
from app.extract_text import extract


@pytest.fixture
def library(tmp_path, monkeypatch):
    c = sqlite3.connect(tmp_path / "index.sqlite", isolation_level=None)
    c.row_factory = sqlite3.Row
    monkeypatch.setattr(db, "conn", lambda: c)
    db.init(); people.init(); search_index.init(); scope.set_owners(None)
    def add(name, owner="alice", cat="image", ext="jpg"):
        return c.execute("INSERT INTO files(path,dir,name,ext,cat,size,mtime,ts,seen,owner) VALUES(?,?,?,?,?,10,100,100,1,?)",
                         (f"/nas/{owner}/{name}", f"/nas/{owner}", name, ext, cat, owner)).lastrowid
    yield c, add
    scope.set_owners(None); c.close()


def add_face(c, fid, name="", owner="alice", vector=None):
    vector = np.eye(128, dtype="float32")[0] if vector is None else vector
    pid = c.execute("INSERT INTO people(name,owner,prototype,created) VALUES(?,?,?,1)", (name, owner, vector.tobytes())).lastrowid
    f = c.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    c.execute("INSERT OR REPLACE INTO face_index VALUES(?,?,?,?,?,1)", (fid, f["path"], f["mtime"], f["size"], "done"))
    face = c.execute("INSERT INTO faces(file_id,person_id,embedding,crop,score) VALUES(?,?,?,?,.99)", (fid, pid, vector.tobytes(), b"fixture")).lastrowid
    return pid, face


def test_conservative_clustering_does_not_merge_ambiguous_or_same_photo():
    a, b = np.eye(128, dtype="float32")[:2]
    bank = np.array([a,b]); feature = (a+b) / np.sqrt(2)
    assert people.choose_person(a, bank, [1,2]) == 1
    assert people.choose_person(a, bank, [1,2], {1}) is None
    assert people.choose_person(feature, bank, [1,2]) is None


def test_names_are_searchable_and_can_be_corrected(library):
    c, add = library
    a, b = add("holiday.jpg"), add("birthday.jpg")
    first, face = add_face(c, a)
    second, other = add_face(c, b)
    people.rename(first, "Alex Example")
    assert queries.query({"text":"Alex"})["items"][0]["id"] == a
    people.merge(second, first)
    assert queries.query({"person_name":"Alex Example"})["total"] == 2
    split = people.correct(other)
    assert split["person_id"] != first
    assert queries.query({"person_id": first})["total"] == 1
    people.correct(face, ignore=True)
    assert queries.query({"person_id": first})["total"] == 0


def test_scope_and_stale_file_guards(library):
    c, add = library
    a = add("one.jpg"); b = add("two.jpg", owner="bob")
    pa, fa = add_face(c,a,"Alice"); pb, fb = add_face(c,b,"Bob","bob")
    scope.set_owners(["alice"])
    assert people.listing()["total"] == 1
    with pytest.raises(HTTPException): people.face(fb)
    with pytest.raises(HTTPException): people.rename(pb,"Wrong scope")
    assert queries.query({"person_name":"Bob"})["total"] == 0
    c.execute("UPDATE files SET mtime=101 WHERE id=?",(a,))
    assert people.listing()["total"] == 0
    with pytest.raises(HTTPException): people.face(fa)


def test_merge_does_not_cross_libraries(library):
    c, add=library
    a,_=add_face(c,add("a.jpg"));b,_=add_face(c,add("b.jpg","bob"),owner="bob")
    with pytest.raises(HTTPException):people.merge(a,b)
    assert people.listing()["total"]==2


def test_clear_biometrics_keeps_original_index(library):
    c, add=library
    a,_=add_face(c,add("a.jpg"));b,_=add_face(c,add("b.jpg","bob"),owner="bob")
    scope.set_owners(["alice"]);people.clear()
    assert c.execute("SELECT COUNT(*) FROM files").fetchone()[0]==2
    assert c.execute("SELECT COUNT(*) FROM faces").fetchone()[0]==1
    assert c.execute("SELECT id FROM people").fetchone()[0]==b


def test_deleting_last_photo_removes_stored_face_data(library):
    c,add=library
    fid=add('one.jpg');add_face(c,fid,'Test person')
    c.execute('DELETE FROM files WHERE id=?',(fid,))
    for table in ('faces','face_index','people'):
        assert c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


def test_search_operators_and_literal_fts(library):
    c, add=library
    a=add("invoice.pdf",cat="document",ext="pdf")
    b=add("other.pdf",cat="document",ext="pdf")
    c.execute("INSERT INTO text_index VALUES(?, '/nas/alice/other.pdf',100,10,'done',30,1)",(b,))
    c.execute("INSERT INTO document_text(rowid,body) VALUES(?,?)",(b,"Invoice for the garden furniture"))
    parsed=search_index.parse('type:pdf invoice owner:alice larger:1b before:2027-01-01')
    assert queries.query(parsed["filter"])["total"]==2
    assert queries.query({"text":"garden"})["total"]==1
    for term in ["\" OR 1=1 --", "*", "%", "NEAR(foo)", "'", 'body:"secret"']:
        queries.query({"text":term})
    c.execute("UPDATE files SET size=11 WHERE id=?",(b,))
    assert queries.query({"text":"garden"})["total"]==0
    assert queries.query({"text":"invoice"})["total"]==1


@pytest.mark.parametrize("query",['type:', 'before:tomorrow', 'larger:lots', '"open quote', 'x'*501])
def test_bad_search_has_clear_error(query):
    with pytest.raises(HTTPException) as e:search_index.parse(query)
    assert e.value.status_code==400


def test_document_extraction(tmp_path):
    path=tmp_path/'note.txt';path.write_text('Meeting about the blue bicycle',encoding='utf8')
    assert 'bicycle' in extract(path,'txt')
    word=tmp_path/'note.docx'
    with zipfile.ZipFile(word,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="urn:w"><w:t>Recipe for pancakes</w:t></w:document>')
    assert 'pancakes' in extract(word,'docx')


def test_index_status_reports_pending_and_indexed_files(library):
    c,add=library
    add('photo.jpg');add('invoice.pdf',cat='document',ext='pdf')
    assert people.status()['total']==1
    assert people.status()['checked']==0
    assert search_index.status()['total']==1
    assert search_index.status()['indexed']==0


def test_celebrity_never_uploads_without_opt_in(library,monkeypatch):
    from app.intelligence_http import celebrity
    monkeypatch.delenv('CELEBRITY_MATCHING_ENABLED',raising=False)
    with pytest.raises(HTTPException) as e:celebrity(1,{"consent":"send-this-crop-to-amazon-rekognition"})
    assert e.value.status_code==409
    monkeypatch.setenv('CELEBRITY_MATCHING_ENABLED','1')
    with pytest.raises(HTTPException) as e:celebrity(1,{})
    assert e.value.status_code==400
