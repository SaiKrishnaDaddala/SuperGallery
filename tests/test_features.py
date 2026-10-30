import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import db, features, intelligence_tasks, jobs, people, search_index, visual_search, albums, queries, rules


@pytest.fixture
def feature_library(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path/'features.db', isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(db, 'conn', lambda: conn)
    monkeypatch.setattr(jobs, '_history', [])
    db.init(); people.init(); search_index.init(); visual_search.init(); albums.init(); intelligence_tasks.init()
    yield conn
    conn.close()


def test_disable_cancels_work_persists_and_does_not_restart_automatically(feature_library, monkeypatch):
    c=feature_library
    task=jobs.Task('visual','test',lambda:None)
    jobs._history.append(task)
    c.execute("INSERT INTO intelligence_requests VALUES(1,'visual','null','queued',0,0)")
    features.update_features(features.Changes(values={'photo_search':False}))
    assert task.cancel_requested
    assert c.execute('SELECT state FROM intelligence_requests').fetchone()[0]=='paused'
    assert json.loads(db.kv_get('features'))['photo_search'] is False
    with pytest.raises(HTTPException) as error: intelligence_tasks.submit('visual')
    assert error.value.status_code==403
    calls=[]
    monkeypatch.setattr(intelligence_tasks,'submit',lambda *a,**kw:calls.append(a))
    # Even a stale queued request cannot restart a disabled capability.
    c.execute("UPDATE intelligence_requests SET state='queued'")
    intelligence_tasks.resume()
    assert calls==[]
    features.update_features(features.Changes(values={'photo_search':True}))
    intelligence_tasks.resume(); intelligence_tasks.refresh_enabled()
    assert calls==[]


def test_text_switches_remove_search_sources_without_deleting_saved_data(feature_library):
    c=feature_library
    c.execute("INSERT INTO files(id,path,dir,name,ext,cat,size,mtime,ts,seen,owner) VALUES(1,'/fixture/photo.png','/fixture','photo.png','png','image',1,1,1,1,'alice')")
    c.execute("INSERT INTO ocr_index VALUES(1,'/fixture/photo.png',1,1,'done',1,0)")
    c.execute("INSERT INTO ocr_text(rowid,body) VALUES(1,'bicycle invoice')")
    assert queries.query({'text':'bicycle'})['total']==1
    features.update_features(features.Changes(values={'ocr':False,'documents':False,'people':False}))
    assert queries.query({'text':'bicycle'})['total']==0
    assert queries.query({'text':'photo'})['total']==1
    assert c.execute('SELECT COUNT(*) FROM ocr_text').fetchone()[0]==1
    with pytest.raises(HTTPException): queries.query({'person_name':'Alex'})
    features.update_features(features.Changes(values={'ocr':True}))
    assert queries.query({'text':'bicycle'})['total']==1


def test_cleanup_disables_scheduled_rules_and_smart_queries(feature_library, monkeypatch):
    features.update_features(features.Changes(values={'cleanup':False}))
    assert not features.enabled('automation')
    monkeypatch.setattr(rules,'load',lambda:pytest.fail('Disabled rules must not be evaluated'))
    rules.due()
    with pytest.raises(jobs.Cancelled):rules.run(SimpleNamespace(), 'unused')
    with pytest.raises(HTTPException):queries.query({'smart':'junk'})
    with pytest.raises(HTTPException):queries.query({'dupes':True})


def test_authenticated_api_enforces_feature_flags_and_strict_values(feature_library, tmp_path, monkeypatch):
    from app import auth_http, discovery_http
    from app.security import Security
    store=Security(tmp_path/'auth', 'test-only-password-123')
    monkeypatch.setattr(auth_http,'security',store)
    app=FastAPI();auth_http.install(app);app.include_router(features.router);app.include_router(discovery_http.router)
    @app.get('/api/people')
    def people_test():return {'ok':True}
    @app.post('/api/upload')
    def upload_test():return {'ok':True}
    @app.get('/api/backups')
    def backup_test():return {'ok':True}
    with TestClient(app,base_url='https://nas.test',headers={'X-SG-Request':'1'}) as client:
        assert client.put('/api/features',json={'values':{'people':False}}).status_code==401
        assert client.post('/api/login',json={'password':'test-only-password-123'}).status_code==200
        assert client.put('/api/features',json={'values':{'people':False}},headers={'Origin':'https://attacker.test'}).status_code==403
        assert client.put('/api/features',json={'values':{'people':'false'}}).status_code==422
        assert client.put('/api/features',json={'values':{'authentication':False}}).status_code==422
        assert client.put('/api/features',json={'values':{'people':False,'uploads':False,'photo_search':False,'video_search':False,'albums':False}}).status_code==200
        assert client.get('/api/people').status_code==403
        assert client.post('/api/upload').status_code==403
        assert client.get('/api/albums').status_code==403
        assert client.get('/api/visual/status').status_code==403
        assert client.post('/api/visual/search',json={'q':'water','media':'video'}).status_code==403
        assert client.get('/api/visual/frame/1').status_code==403
        assert client.post('/api/intelligence/index',json={'kind':'visual'}).status_code==403
        assert client.get('/api/backups').status_code==200
        assert client.get('/api/security').status_code==200
        assert client.put('/api/features',json={'values':{'people':True}}).status_code==200
        assert client.get('/api/people').status_code==200


def test_all_flags_default_enabled_for_existing_installations(feature_library):
    assert all(features.settings().values())
    features.update_features(features.Changes(values={key:False for key in features.CATALOG}))
    assert not any(features.settings().values())
    assert features.describe()['version']=='2.5.0'
