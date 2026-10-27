import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import albums, backups, db, fileops, intelligence_tasks, jobs, ocr_index, people, queries, scope, search_index, uploads_http, visual_search


@pytest.fixture
def library(tmp_path, monkeypatch):
    c=sqlite3.connect(tmp_path/'index.db',isolation_level=None,check_same_thread=False)
    c.row_factory=sqlite3.Row
    monkeypatch.setattr(db,'conn',lambda:c)
    monkeypatch.setattr(backups,'CONFIG_DIR',tmp_path)
    monkeypatch.setattr(uploads_http,'CONFIG_DIR',tmp_path)
    db.init();people.init();search_index.init();visual_search.init();albums.init();intelligence_tasks.init()
    scope.set_owners(None)
    def add(name,owner='alice',cat='image',data=b'fixture'):
        folder=tmp_path/owner;folder.mkdir(exist_ok=True)
        path=folder/name;path.write_bytes(data);st=path.stat()
        fid=c.execute('INSERT INTO files(path,dir,name,ext,cat,size,mtime,ts,seen,owner) VALUES(?,?,?,?,?,?,?,?,1,?)',
            (path.as_posix(),folder.as_posix(),name,path.suffix[1:],cat,st.st_size,st.st_mtime,st.st_mtime,owner)).lastrowid
        return fid,path
    yield c,add,tmp_path
    scope.set_owners(None)
    try:c.close()
    except sqlite3.Error:pass


def vector(c,fid,embedding,seconds=0,preview=None):
    r=c.execute('SELECT * FROM files WHERE id=?',(fid,)).fetchone()
    c.execute('INSERT OR REPLACE INTO visual_index VALUES(?,?,?,?,?,?,?,?,0)',(fid,r['path'],r['mtime'],r['size'],visual_search.MODEL,'done',1,15 if preview else 0))
    return c.execute('INSERT INTO visual_vectors(file_id,seconds,embedding,preview) VALUES(?,?,?,?)',(fid,seconds,np.asarray(embedding,dtype='<f2').tobytes(),preview)).lastrowid


def test_visual_ranking_filters_scope_and_staleness(library,monkeypatch):
    c,add,_=library
    a,_=add('water.jpg');b,_=add('road.jpg');other,_=add('private.jpg','bob')
    axis=np.eye(512,dtype='float32')
    for fid,v in [(a,axis[0]),(b,axis[1]),(other,axis[0])]:vector(c,fid,v)
    monkeypatch.setattr(visual_search,'text_embedding',lambda text:axis[0])
    scope.set_owners(['alice'])
    assert [i['id'] for i in visual_search.search('drinking water')['items']]==[a]
    assert visual_search.search('water',{'owner':'bob'})['total']==0
    c.execute('UPDATE files SET size=size+1 WHERE id=?',(a,))
    assert visual_search.search('water')['items']==[]
    c.execute('DELETE FROM files WHERE id=?',(b,))
    assert not c.execute('SELECT 1 FROM visual_vectors WHERE file_id=?',(b,)).fetchone()


def test_video_best_scene_and_preview_access(library,monkeypatch):
    c,add,_=library;fid,_=add('ride.mp4',cat='video')
    axis=np.eye(512,dtype='float32');vector(c,fid,axis[1],1,b'first');scene=vector(c,fid,axis[0],30,b'matched')
    monkeypatch.setattr(visual_search,'text_embedding',lambda text:axis[0])
    result=visual_search.search('cycling',media='video')['items']
    assert len(result)==1 and result[0]['start_seconds']==30 and result[0]['scene_id']==scene
    assert visual_search.frame(scene)==b'matched'
    scope.set_owners(['bob'])
    with pytest.raises(HTTPException):visual_search.frame(scene)


@pytest.mark.parametrize('duration',[.5,5,30,3600,100000])
def test_video_sampling_covers_duration_with_bounded_work(duration):
    times,interval=visual_search.sample_times(duration)
    assert 1<=len(times)<=120 and all(0<=t<duration for t in times)
    assert times==sorted(set(times)) and interval>=15
    assert duration-times[-1]<=max(15,duration/120)+1


def test_ocr_text_literal_search_stale_and_delete(library):
    c,add,_=library;fid,path=add('receipt.png')
    row=c.execute('SELECT * FROM files WHERE id=?',(fid,)).fetchone()
    c.execute('INSERT INTO ocr_index VALUES(?,?,?,?,?,?,0)',(fid,path.as_posix(),row['mtime'],row['size'],'done',1))
    c.execute('INSERT INTO ocr_text(rowid,body) VALUES(?,?)',(fid,'BICYCLE RECEIPT 1042'))
    assert ocr_index.status()['indexed']==1
    assert ocr_index.status()['checked']==1
    assert queries.query({'text':'bicycle'})['total']==1
    scope.set_owners(['bob']);assert queries.query({'text':'bicycle'})['total']==0
    scope.set_owners(None);c.execute('UPDATE files SET mtime=mtime+10 WHERE id=?',(fid,))
    assert queries.query({'text':'bicycle'})['total']==0
    assert ocr_index.status()['indexed']==0
    c.execute('DELETE FROM files WHERE id=?',(fid,))
    assert c.execute('SELECT COUNT(*) FROM ocr_text').fetchone()[0]==0


def test_smart_album_preserves_filters_and_originals(library):
    c,add,_=library;add('original.jpg')
    definition={'mode':'photos','q':'people cycling','filter':{'owner':'alice','after':1700000000},'sort':'ts','order':'desc'}
    aid=albums.save('Weekend rides',definition)['id']
    albums.save('Bike rides',definition,aid)
    assert albums.listing()['items'][0]['definition']==definition
    albums.remove(aid)
    assert albums.listing()['items']==[] and c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==1


def test_backup_restores_metadata_keeps_current_trash_and_credentials(library,monkeypatch):
    c,add,root=library;add('original.jpg')
    aid=albums.save('Before',{'mode':'photos','q':'water'})['id']
    (root/'secret.key').write_text('fixture-credential')
    saved=backups.snapshot();assert backups.verify(saved['id'])['originals_included'] is False
    with zipfile.ZipFile(backups.export(saved['id'])) as archive:
        assert set(archive.namelist())=={'index.db','manifest.json'}
        assert hashlib.sha256(archive.read('index.db')).hexdigest()==json.loads(archive.read('manifest.json'))['sha256']
    albums.save('Changed',{'mode':'photos','q':'water'},aid)
    c.execute("INSERT INTO trash(orig_path,trash_path,size,is_dir,deleted_at,reason) VALUES('old','bin',20,0,1,'manual')")
    db.kv_set('rules',[{'danger':'old rule'}]);db.kv_set('last_scan',123)
    monkeypatch.setattr(jobs,'history',lambda:[])
    backups.stage(saved['id']);c.close();backups.apply_pending()
    with sqlite3.connect(root/'index.db') as restored:
        assert restored.execute('SELECT name FROM smart_albums').fetchone()[0]=='Before'
        assert restored.execute('SELECT COUNT(*) FROM trash').fetchone()[0]==1
        assert restored.execute("SELECT v FROM kv WHERE k='rules'").fetchone()[0]=='[]'
        assert not restored.execute("SELECT v FROM kv WHERE k='last_scan'").fetchone()
    assert (root/'secret.key').read_text()=='fixture-credential' and not backups.pending()
    assert len(backups.listing()['items'])==2


def test_tampered_backup_and_busy_restore_are_rejected(library,monkeypatch):
    _,add,root=library;add('photo.jpg');saved=backups.snapshot()
    monkeypatch.setattr(jobs,'history',lambda:[{'status':'running'}])
    with pytest.raises(HTTPException):backups.stage(saved['id'])
    assert not backups.pending()
    with (backups.resolve(saved['id'])/'index.db').open('ab') as stream:stream.write(b'corrupt')
    with pytest.raises(HTTPException):backups.verify(saved['id'])


def test_duplicate_refuses_missing_or_changed_survivor(library,monkeypatch):
    c,add,_=library;a,path=add('copy.jpg');b,keeper=add('original.jpg')
    monkeypatch.setattr(fileops,'safe_path',lambda p:p)
    c.execute("UPDATE files SET hash='same'")
    fileops.verify_duplicate_survivor(path.as_posix(),{a})
    with pytest.raises(fileops.OpError):fileops.verify_duplicate_survivor(path.as_posix(),{a,b})
    keeper.write_bytes(b'changed')
    with pytest.raises(fileops.OpError):fileops.verify_duplicate_survivor(path.as_posix(),{a})
    assert path.exists()


def test_upload_verified_retries_resume_no_overwrite_and_session_guard(library,monkeypatch):
    _,_,root=library;dest=root/'alice';dest.mkdir();(dest/'note.txt').write_text('original')
    def confined(path):
        p=Path(path).resolve()
        if dest not in [p,*p.parents]:raise fileops.OpError('outside library')
        return p.as_posix()
    monkeypatch.setattr(fileops,'safe_path',confined)
    monkeypatch.setattr(uploads_http.scanner,'index_file',lambda p:None)
    from app import main
    monkeypatch.setattr(main,'start_index',lambda *a,**kw:None)
    app=FastAPI()
    @app.middleware('http')
    async def session(request,call_next):
        request.state.session={'id':request.headers.get('test-session','one')}
        return await call_next(request)
    app.include_router(uploads_http.router)
    client=TestClient(app)
    body={'name':'note.txt','size':6,'destination':dest.as_posix(),'fingerprint':'a'*64}
    started=client.post('/api/uploads',json=body).json();uid=started['id']
    url='/api/uploads/'+uid
    assert client.put(url,content=b'abc',headers={'x-chunk-sha256':'b'*64}).status_code==400
    chunk={'x-chunk-sha256':hashlib.sha256(b'abc').hexdigest()}
    assert client.put(url,content=b'abc',headers=chunk).json()['offset']==3
    assert client.put(url,content=b'abc',headers=chunk).json()['offset']==3
    assert client.post('/api/uploads',json=body).json()['offset']==3
    assert client.post(url+'/finish',json={}).status_code==409
    assert client.put(url+'?offset=3',content=b'abc',headers={**chunk,'test-session':'two'}).status_code==404
    assert client.put(url+'?offset=3',content=b'abc',headers=chunk).json()['offset']==6
    result=client.post(url+'/finish',json={});assert result.status_code==200,result.text
    assert Path(result.json()['path']).read_bytes()==b'abcabc'
    assert (dest/'note.txt').read_text()=='original'
    assert client.post(url+'/finish',json={}).json()==result.json()
    assert client.post('/api/uploads',json={**body,'destination':root.as_posix()}).status_code==400


def test_index_batches_are_fair_stable_and_do_not_retry_errors_forever(library,monkeypatch):
    c,add,_=library
    for i in range(101):add(str(i)+'.jpg')
    monkeypatch.setattr(visual_search,'session',lambda kind:None)
    monkeypatch.setattr(fileops,'safe_path',lambda path:path)
    task=jobs.Task('visual','test',None)
    req=c.execute("INSERT INTO intelligence_requests(kind,owners,state,created,updated) VALUES('visual','null','queued',0,0)").lastrowid
    result=intelligence_tasks._execute(task,req,'visual',None,True)
    assert result['_continue'] is True and task.done==100 and task.total==101
    assert c.execute('SELECT state FROM intelligence_requests WHERE id=?',(req,)).fetchone()[0]=='queued'
    result=intelligence_tasks._execute(task,req,'visual',None,True)
    assert '_continue' not in result and task.done==101
    assert c.execute('SELECT COUNT(*) FROM visual_index').fetchone()[0]==101
    assert c.execute('SELECT state FROM intelligence_requests WHERE id=?',(req,)).fetchone()[0]=='done'
