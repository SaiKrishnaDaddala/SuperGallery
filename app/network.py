"""Explicit external origin and trusted reverse-proxy handling; local-only by default."""
import ipaddress
import json
import os
import threading
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .config import CONFIG_DIR

router=APIRouter(prefix='/api/network')
_lock=threading.RLock()


def public_origin(value):
    value=value.strip()
    if not value:return ''
    try:
        u=urlsplit(value)
        port=u.port
        host=(u.hostname or '').encode('idna').decode('ascii').lower()
        if u.scheme!='https' or not host or u.username is not None or u.password is not None or u.path not in ('','/') or u.query or u.fragment or any(c.isspace() for c in value) or '*' in value:
            raise ValueError()
        if ':' in host:host='['+host+']'
        return 'https://'+host+(f':{port}' if port and port!=443 else '')
    except (ValueError,UnicodeError):
        raise HTTPException(422,'Use an HTTPS address without a path, password, query or wildcard.')


def proxy_addresses(values):
    try:
        return sorted({str(ipaddress.ip_address(v.strip())) for v in values if v.strip()})
    except ValueError:
        raise HTTPException(422,'Trusted proxies must be exact IP addresses, not ranges or wildcards.')


def settings():
    path=CONFIG_DIR/'network.json'
    with _lock:
        if path.exists():
            result=json.loads(path.read_text(encoding='utf-8'))
        else:
            result={'enabled':os.getenv('REMOTE_ACCESS_ENABLED')=='1','public_url':os.getenv('PUBLIC_URL',''),
                    'trusted_proxies':os.getenv('TRUSTED_PROXIES','').split(','),
                    'https_only_gateway':os.getenv('GATEWAY_HTTPS_ONLY')=='1'}
    return {'enabled':result.get('enabled') is True,'public_url':public_origin(result.get('public_url','')),
            'trusted_proxies':proxy_addresses(result.get('trusted_proxies',[])),
            'https_only_gateway':result.get('https_only_gateway') is True}


def host(request):
    raw=request.headers.get('host','')
    if any(c.isspace() for c in raw) or any(c in raw for c in '/\\@?#'):
        raise HTTPException(400,'Invalid host header')
    try:
        u=urlsplit('//'+raw);u.port
        return (u.hostname or '').lower(),u.netloc.lower()
    except ValueError:
        raise HTTPException(400,'Invalid host header')


def private_peer(value):
    try:return ipaddress.ip_address(value).is_private
    except ValueError:return False


LAN_NETWORKS=[ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8','169.254.0.0/16','::1/128','fc00::/7','fe80::/10')]


def private_ip_host(hostname):
    """A private IP typed into the address bar needs no allowlist entry: DNS rebinding relies on a
    domain name, never an IP literal, so this keeps working when the NAS gets a new LAN address."""
    try:ip=ipaddress.ip_address(hostname)
    except ValueError:return False
    return any(ip in net for net in LAN_NETWORKS)


def apply_transport(request):
    """Run before URL evaluation or authentication. Never trust headers from arbitrary peers."""
    hostname,authority=host(request)
    cfg=settings()
    external=urlsplit(cfg['public_url']).netloc.lower() if cfg['public_url'] else ''
    peer=request.client.host if request.client else ''
    request.state.remote=False
    if external and authority in (external,external+':443'):
        if not cfg['enabled']:
            raise HTTPException(403,'Remote access is off. Open SuperGallery using its local NAS address.')
        request.state.remote=True
        if request.scope['scheme']!='https':
            # Some HTTPS-only gateways report their internal HTTP hop in XFP.
            # This explicit operator assertion applies only to the exact configured
            # public origin and exact proxy peers, never to arbitrary Host values.
            if peer not in cfg['trusted_proxies'] or (not cfg['https_only_gateway'] and request.headers.get('x-forwarded-proto','').lower()!='https'):
                raise HTTPException(426,'Remote access needs HTTPS or a configured trusted proxy forwarding X-Forwarded-Proto: https.')
            request.scope['scheme']='https'
        request.state.public_origin=cfg['public_url']
        return
    local=[v.strip().lower() for v in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,::1').split(',') if v.strip()]
    if hostname not in local and not private_ip_host(hostname):
        raise HTTPException(400,'Invalid host header. Add your local NAS name to ALLOWED_HOSTS, or configure Remote access in Settings.')
    # A public client cannot bypass local-only mode by supplying a local Host name.
    if not private_peer(peer) and peer!='testclient':
        raise HTTPException(403,'Use the configured external address for remote access.')


class NetworkChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:StrictBool
    public_url:str=Field('',max_length=300)
    trusted_proxies:list[str]=Field(default_factory=list,max_length=8)
    https_only_gateway:StrictBool=False
    password:str=Field(max_length=1024)
    code:str=Field('',max_length=80)


@router.get('')
def status(request:Request):
    from .auth_http import security
    return {**settings(),'remote_session':getattr(request.state,'remote',False),'mfa_enabled':security.enabled(),
            'proxy_peer':request.client.host if request.client else None,
            'forwarded_https':request.headers.get('x-forwarded-proto','').lower()=='https'}


@router.put('')
def update(body:NetworkChange,request:Request):
    from .auth_http import security,require_private,client
    require_private(request)
    origin=public_origin(body.public_url)
    proxies=proxy_addresses(body.trusted_proxies)
    if body.enabled and not origin:raise HTTPException(422,'Enter the external HTTPS address first.')
    if body.https_only_gateway and not proxies:raise HTTPException(422,'An HTTPS-only gateway needs at least one exact trusted proxy IP.')
    if body.enabled and not security.enabled():raise HTTPException(409,'Enable two-step verification before enabling remote access.')
    # Perform changes locally to avoid losing the only access path or trusting a remote-supplied proxy.
    if getattr(request.state,'remote',False):raise HTTPException(403,'Change remote access from the local NAS address.')
    security.reauthenticate(body.password,client(request))
    with security.tx() as c:
        if security.enabled() and not security._verify_factor(c,body.code):
            raise HTTPException(403,'Enter a valid authenticator or recovery code.')
    value={'enabled':body.enabled,'public_url':origin,'trusted_proxies':proxies,'https_only_gateway':body.https_only_gateway}
    with _lock:
        target=CONFIG_DIR/'network.json';temporary=CONFIG_DIR/'network.json.tmp'
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f)
        os.replace(temporary,target)
    return {**value,'ok':True}
