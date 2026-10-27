"""Chunked uploads with verified retry, atomic publication and no original overwrites."""
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from . import fileops, scanner, queries, scope
from .config import CONFIG_DIR

router=APIRouter(prefix='/api/uploads')
CHUNK=4*1024*1024
_lock=threading.RLock()


def safe_path(path):
    try:
        resolved=fileops.safe_path(path)
        if scope.owners() and not any(resolved==base or resolved.startswith(base+'/') for base in scope.bases()):
            raise HTTPException(403,'Choose a folder in the selected library.')
        return resolved
    except fileops.OpError as exc:raise HTTPException(400,str(exc)) from exc


def root():
    p=CONFIG_DIR/'uploads';p.mkdir(mode=0o700,exist_ok=True)
    return p


def paths(upload_id):
    if not re.fullmatch(r'[a-f0-9]{32}',upload_id):raise HTTPException(400,'Invalid upload.')
    return root()/(upload_id+'.json'),root()/(upload_id+'.part')


def write(meta):
    path,_=paths(meta['id']);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(meta));temp.chmod(0o600);os.replace(temp,path)


def load(upload_id,request):
    path,part=paths(upload_id)
    try:meta=json.loads(path.read_text())
    except (OSError,ValueError):raise HTTPException(404,'Upload expired. Select the file again.')
    if meta['session']!=request.state.session['id']:raise HTTPException(404,'Upload not found in this session.')
    safe_path(meta['destination'])
    return meta,part


class Start(BaseModel):
    name:str=Field(min_length=1,max_length=240)
    size:int=Field(ge=0,le=100*1024**3)
    destination:str=Field(min_length=1,max_length=4096)
    fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')


@router.post('')
def start(body:Start,request:Request):
    name=body.name
    if name in ('.','..') or any(c in name for c in '/\\\x00') or any(ord(c)<32 for c in name):
        raise HTTPException(400,'Choose a simple file name without folders or control characters.')
    destination=safe_path(body.destination)
    if not os.path.isdir(destination):raise HTTPException(400,'Choose an existing destination folder.')
    with _lock:
        active=0
        for path in root().glob('*.json'):
            try:
                m=json.loads(path.read_text())
                if time.time()-m['updated']>7*86400:
                    path.with_suffix('.part').unlink(missing_ok=True);path.unlink();continue
                if m['session']==request.state.session['id']:
                    active+=not m.get('complete')
                    if all(m[k]==v for k,v in {'fingerprint':body.fingerprint,'name':name,'destination':destination,'size':body.size}.items()):
                        part=path.with_suffix('.part')
                        return {'id':m['id'],'offset':part.stat().st_size if part.exists() else 0,'chunk_size':CHUNK,'complete':m.get('complete',False)}
            except (OSError,ValueError,KeyError):continue
        if active>=20:raise HTTPException(409,'Finish or cancel existing uploads before adding more.')
        if shutil.disk_usage(root()).free<body.size+128*1024**2:raise HTTPException(507,'Not enough NAS space to receive this file.')
        meta={'id':secrets.token_hex(16),'session':request.state.session['id'],'name':name,'size':body.size,
            'destination':destination,'fingerprint':body.fingerprint,'updated':time.time()}
        _,part=paths(meta['id']);part.touch(mode=0o600);write(meta)
        return {'id':meta['id'],'offset':0,'chunk_size':CHUNK,'complete':False}


@router.put('/{upload_id}')
async def chunk(upload_id:str,request:Request,offset:int=0):
    if offset<0:raise HTTPException(400,'Invalid upload offset.')
    payload=bytearray()
    async for data in request.stream():
        payload.extend(data)
        if len(payload)>CHUNK:raise HTTPException(413,'Send chunks no larger than 4 MB.')
    expected=request.headers.get('x-chunk-sha256','')
    if not re.fullmatch(r'[a-f0-9]{64}',expected) or hashlib.sha256(payload).hexdigest()!=expected:
        raise HTTPException(400,'Chunk verification failed. Retry this chunk.')
    with _lock:
        meta,part=load(upload_id,request)
        if meta.get('complete'):raise HTTPException(409,'This upload is already complete.')
        current=part.stat().st_size
        if offset<current:
            with part.open('rb') as f:f.seek(offset);previous=f.read(len(payload))
            if previous==payload:return {'offset':current}
            raise HTTPException(409,'This chunk differs from the uploaded data. Restart the upload.')
        if offset!=current or current+len(payload)>meta['size']:
            raise HTTPException(409,'Upload offset changed. Resume from the server position.')
        with part.open('ab') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        meta['updated']=time.time();write(meta)
        return {'offset':current+len(payload)}


@router.post('/{upload_id}/finish')
def finish(upload_id:str,request:Request):
    with _lock:
        meta,part=load(upload_id,request)
        if meta.get('complete'):return {'ok':True,'path':meta['path']}
        if part.stat().st_size!=meta['size']:raise HTTPException(409,'The file has not finished uploading.')
        destination=safe_path(meta['destination'])
        target=fileops.unique_dest(str(Path(destination)/meta['name']))
        safe_path(target)
        temporary=Path(destination)/('.sg-upload-'+upload_id)
        try:
            shutil.copyfile(part,temporary)
            if temporary.stat().st_size!=meta['size']:raise OSError('Incomplete file copy')
            # Reserve the final name atomically; never overwrite an existing original.
            while True:
                try:
                    with open(target,'xb'):pass
                    break
                except FileExistsError:
                    target=fileops.unique_dest(target)
            try:os.replace(temporary,target)
            except BaseException:
                Path(target).unlink(missing_ok=True);raise
        finally:
            temporary.unlink(missing_ok=True)
        scanner.index_file(target);queries.invalidate()
        meta.update(complete=True,path=target,updated=time.time());write(meta);part.unlink()
        from .main import start_index
        start_index('Index uploaded files',rescan=False)
        return {'ok':True,'path':target}


@router.post('/{upload_id}/cancel')
def cancel(upload_id:str,request:Request):
    with _lock:
        meta,part=load(upload_id,request)
        path,_=paths(upload_id);part.unlink(missing_ok=True);path.unlink()
    return {'ok':True}
