"""Validated API for visual search, OCR, saved searches and indexing."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, FiniteFloat, ValidationError
from . import albums, features, intelligence_tasks, ocr_index, scope, search_index, visual_search

router=APIRouter(prefix='/api')


class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    owner: str | None=Field(None,max_length=100)
    person_id: int | None=Field(None,ge=1)
    person_name: str | None=Field(None,max_length=80)
    dir: str | None=Field(None,max_length=4096)
    path_q: str | None=Field(None,max_length=4096)
    q: str | None=Field(None,max_length=500)
    after: FiniteFloat | None=None
    before: FiniteFloat | None=None
    min_size: int | None=Field(None,ge=0)
    max_size: int | None=Field(None,ge=0)
    cat: list[str] | None=Field(None,max_length=12)
    ext: list[str] | None=Field(None,max_length=20)


class Search(BaseModel):
    q: str=Field(min_length=1,max_length=500)
    filter: Filters=Field(default_factory=Filters)
    media: Literal['image','video']='image'
    limit: int=Field(60,ge=1,le=60)
    offset: int=Field(0,ge=0,le=180)


@router.post('/visual/search')
def visual_query(body: Search):
    features.require('video_search' if body.media == 'video' else 'photo_search')
    parsed=search_index.parse(body.q)
    phrase=parsed['filter'].pop('text','')
    try:
        filters=Filters(**{**body.filter.model_dump(exclude_none=True),**parsed['filter']}).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise HTTPException(400,'One of the search filters is invalid or too long.') from exc
    return {**visual_search.search(phrase,filters,body.media,body.limit,body.offset),'labels':parsed['labels']}


@router.get('/visual/status')
def visual_status(media: Literal['image','video']='image'):
    features.require('video_search' if media == 'video' else 'photo_search')
    return visual_search.status(media)


@router.get('/visual/frame/{scene_id}')
def visual_frame(scene_id: int):
    features.require('video_search')
    return Response(visual_search.frame(scene_id),media_type='image/jpeg',headers={'Cache-Control':'no-store'})


@router.get('/ocr/status')
def ocr_status():
    return ocr_index.status()


class IndexRequest(BaseModel):
    kind: Literal['visual','scenes','ocr','faces','documents']
    retry: bool=False


@router.post('/intelligence/index')
def start_intelligence(body: IndexRequest):
    task=intelligence_tasks.submit(body.kind,scope.owners(),body.retry)
    return {'task':task.id}


class Definition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Literal['files','photos','videos']='files'
    q: str=Field('',max_length=500)
    filter: Filters=Field(default_factory=Filters)
    sort: Literal['ts','name','size']='ts'
    order: Literal['asc','desc']='desc'


class AlbumRequest(BaseModel):
    name: str=Field(min_length=1,max_length=80)
    definition: Definition
    id: int | None=Field(None,ge=1)


@router.get('/albums')
def get_albums():
    return albums.listing()


@router.post('/albums')
def save_album(body: AlbumRequest):
    return albums.save(body.name,body.definition.model_dump(exclude_none=True),body.id)


@router.post('/albums/{album_id}/remove')
def remove_album(album_id: int):
    return albums.remove(album_id)
