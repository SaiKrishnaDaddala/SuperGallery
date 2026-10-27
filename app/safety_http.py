from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse
from . import backups, jobs
from .auth_http import client, require_private, security

router=APIRouter(prefix='/api/backups')


@router.get('')
def listing():
    return backups.listing()


@router.post('')
def create(request:Request):
    require_private(request)
    if jobs.ops.busy_with('backup'):raise HTTPException(409,'A backup is already running.')
    task=jobs.ops.submit(jobs.Task('backup','Back up app data',backups.snapshot))
    return {'task':task.id}


@router.post('/{backup_id}/verify')
def verify(backup_id:str):
    return backups.verify(backup_id)


@router.get('/{backup_id}/download')
def download(backup_id:str,request:Request):
    require_private(request)
    return FileResponse(backups.export(backup_id),filename='supergallery-app-data-'+backup_id+'.zip',media_type='application/zip',headers={'Cache-Control':'no-store'})


@router.post('/{backup_id}/restore')
def restore(backup_id:str,request:Request,body:dict=Body(...)):
    require_private(request)
    if body.get('confirm')!='restore-app-data':raise HTTPException(400,'Confirm the app-data restore.')
    security.reauthenticate(body.get('password'),client(request))
    valid=True
    with security.tx() as c:
        if security.get(c,'totp'):valid=security._verify_factor(c,body.get('code'))
    if not valid:raise HTTPException(403,'Enter a valid authenticator or recovery code.')
    return backups.stage(backup_id)


@router.post('/cancel-restore')
def cancel_restore(request:Request):
    require_private(request)
    return backups.cancel()
