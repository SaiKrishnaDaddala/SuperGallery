import json
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import auth_http, network
from app.security import Security, COOKIE


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(network,'CONFIG_DIR',tmp_path)
    monkeypatch.setenv('ALLOWED_HOSTS','nas.test,localhost,127.0.0.1')
    monkeypatch.delenv('REMOTE_ACCESS_ENABLED',raising=False)
    monkeypatch.delenv('PUBLIC_URL',raising=False)
    monkeypatch.delenv('TRUSTED_PROXIES',raising=False)
    store=Security(tmp_path/'security','test-only-password-123')
    monkeypatch.setattr(auth_http,'security',store)
    app=FastAPI();auth_http.install(app);app.include_router(network.router)
    @app.get('/api/protected')
    def protected():return {'ok':True}
    @app.get('/')
    def root():return {'ok':True}
    return app,store,tmp_path


def configure(root, enabled=True):
    (root/'network.json').write_text(json.dumps({'enabled':enabled,'public_url':'https://gallery.example.com','trusted_proxies':['172.18.0.1']}))


def test_remote_disabled_blocks_origin_even_with_existing_session(gateway,monkeypatch):
    app,store,root=gateway;configure(root,False)
    token=store.login('test-only-password-123','fixture')['session']
    with TestClient(app,base_url='https://gallery.example.com',client=('172.18.0.1',123)) as c:
        c.cookies.set(COOKIE,token)
        assert c.get('/').status_code==403
        assert c.get('/api/protected').status_code==403
    with TestClient(app,base_url='https://nas.test') as c:
        assert c.get('/api/auth').status_code==200


def test_trusted_gateway_preserves_external_https_and_secure_cookie(gateway,monkeypatch):
    app,store,root=gateway;configure(root)
    # Transport test: actual OTP replay/consumption is covered by security tests.
    monkeypatch.setattr(store,'enabled',lambda:True)
    with TestClient(app,base_url='http://gallery.example.com',client=('172.18.0.1',123),headers={'X-Forwarded-Proto':'https','X-SG-Request':'1'}) as c:
        state=c.get('/api/auth')
        assert state.status_code==200 and state.json()['https_required'] is False
        assert state.json()['secure_url']=='https://gallery.example.com/#/settings'
        login=c.post('/api/login',json={'password':'test-only-password-123'},headers={'Origin':'https://gallery.example.com'})
        assert login.status_code==200
        assert 'secure' in login.headers['set-cookie'].lower()
        assert c.post('/api/login',json={'password':'test-only-password-123'},headers={'Origin':'https://attacker.example'}).status_code==403


@pytest.mark.parametrize('peer,proto',[('172.18.0.2','https'),('172.18.0.1','http'),('172.18.0.1','https,http'),('203.0.113.50','https')])
def test_spoofed_or_missing_secure_proxy_headers_fail_closed(gateway,peer,proto):
    app,_,root=gateway;configure(root)
    with TestClient(app,base_url='http://gallery.example.com',client=(peer,123),headers={'X-Forwarded-Proto':proto}) as c:
        assert c.get('/api/auth').status_code==426


def test_remote_requires_mfa_and_settings_require_reauthentication(gateway):
    app,store,root=gateway;configure(root)
    with TestClient(app,base_url='https://gallery.example.com') as c:
        assert c.get('/api/auth').status_code==403
    configure(root,False)
    with TestClient(app,base_url='https://nas.test',headers={'X-SG-Request':'1'}) as c:
        assert c.post('/api/login',json={'password':'test-only-password-123'}).status_code==200
        body={'enabled':True,'public_url':'https://gallery.example.com','trusted_proxies':[],'password':'test-only-password-123'}
        assert c.put('/api/network',json=body).status_code==409
        body.update(enabled=False,password='wrong')
        assert c.put('/api/network',json=body).status_code in (401,403)
        assert not network.settings()['enabled']


@pytest.mark.parametrize('value',['http://gallery.example.com','https://user:secret@gallery.example.com','https://gallery.example.com/path','https://*.example.com','https://gallery.example.com/?token=bad'])
def test_public_address_must_be_an_exact_https_origin(value):
    with pytest.raises(HTTPException):network.public_origin(value)


def test_unknown_hosts_and_proxy_wildcards_rejected(gateway):
    app,_,_=gateway
    with TestClient(app,base_url='https://attacker.example') as c:
        assert c.get('/api/auth').status_code==400
    with pytest.raises(HTTPException):network.proxy_addresses(['*'])
    with pytest.raises(HTTPException):network.proxy_addresses(['172.18.0.0/16'])


def test_https_only_gateway_is_explicit_and_scoped(gateway,monkeypatch):
    app,store,root=gateway;configure(root)
    monkeypatch.setattr(store,'enabled',lambda:True)
    cfg=json.loads((root/'network.json').read_text());cfg['https_only_gateway']=True
    (root/'network.json').write_text(json.dumps(cfg))
    with TestClient(app,base_url='http://gallery.example.com',client=('172.18.0.1',123),headers={'X-Forwarded-Proto':'http'}) as c:
        result=c.post('/api/login',json={'password':'test-only-password-123'},headers={'Origin':'https://gallery.example.com'})
        assert result.status_code==200 and 'secure' in result.headers['set-cookie'].lower()
    with TestClient(app,base_url='http://gallery.example.com',client=('172.18.0.2',123)) as c:
        assert c.get('/').status_code==426
    with TestClient(app,base_url='http://evil.example.com',client=('172.18.0.1',123)) as c:
        assert c.get('/').status_code==400
    cfg['enabled']=False;(root/'network.json').write_text(json.dumps(cfg))
    with TestClient(app,base_url='http://gallery.example.com',client=('172.18.0.1',123)) as c:
        assert c.get('/').status_code==403


@pytest.mark.parametrize('address',['172.16.29.111','192.168.29.41','10.0.0.5'])
def test_private_ip_addresses_work_without_an_allowlist_entry(gateway,address):
    app,_,_=gateway
    with TestClient(app,base_url=f'http://{address}:8800',client=('192.168.29.20',123)) as c:
        assert c.get('/api/auth').status_code==200


@pytest.mark.parametrize('address',['8.8.8.8','203.0.113.9','100.64.0.7','nas.attacker.example'])
def test_public_ips_and_unknown_names_still_need_an_allowlist_entry(gateway,address):
    app,_,_=gateway
    with TestClient(app,base_url=f'http://{address}:8800',client=('192.168.29.20',123)) as c:
        assert c.get('/api/auth').status_code==400


def test_private_ip_host_does_not_let_public_clients_in(gateway):
    app,_,_=gateway
    with TestClient(app,base_url='http://172.16.29.111:8800',client=('8.8.4.4',123)) as c:
        assert c.get('/api/auth').status_code==403
