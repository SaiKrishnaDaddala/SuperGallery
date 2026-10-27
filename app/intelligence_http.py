"""Authenticated People and search endpoints."""
import os
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response
from . import jobs, people, scope, search_index, intelligence_tasks

router = APIRouter(prefix="/api")


@router.post("/search/parse")
def parse_search(body: dict = Body(...)):
    return search_index.parse(body.get("q", ""))


@router.get("/search/status")
def search_status():
    return search_index.status()


@router.post("/search/index")
def search_documents(body: dict = Body(default={})):
    if jobs.intelligence.busy_with("documents"):
        raise HTTPException(409, "Document indexing is already running")
    task = intelligence_tasks.submit('documents', scope.owners(), bool(body.get('retry')))
    return {"task": task.id}


@router.post("/search/clear")
def clear_search():
    return search_index.clear()


@router.get("/people/status")
def people_status():
    return people.status()


@router.get("/people")
def people_list(q: str = Query("", max_length=80), offset: int = Query(0, ge=0), limit: int = Query(120, ge=1, le=200)):
    return people.listing(q, offset, limit)


@router.post("/people/index")
def people_index(body: dict = Body(default={})):
    if jobs.intelligence.busy_with("faces"):
        raise HTTPException(409, "People indexing is already running")
    task = intelligence_tasks.submit('faces', scope.owners(), bool(body.get('retry')))
    return {"task": task.id}


@router.post("/people/clear")
def people_clear():
    return people.clear()


@router.get("/people/{pid}")
def person_detail(pid: int, offset: int = Query(0, ge=0), limit: int = Query(120, ge=1, le=200)):
    return people.detail(pid, offset, limit)


@router.post("/people/{pid}/name")
def person_name(pid: int, body: dict = Body(...)):
    return people.rename(pid, body.get("name", ""))


@router.post("/people/{pid}/merge")
def person_merge(pid: int, body: dict = Body(...)):
    try:
        target = int(body["target"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "Choose a person to merge into")
    return people.merge(pid, target)


@router.get("/faces/{fid}/image")
def face_image(fid: int):
    return Response(people.face(fid)["crop"], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/faces/{fid}/correct")
def face_correct(fid: int, body: dict = Body(...)):
    target = body.get("target")
    if target is not None and (not isinstance(target, int) or isinstance(target, bool)):
        raise HTTPException(400, "Choose a valid person")
    return people.correct(fid, target, body.get("ignore") is True)


@router.post("/faces/{fid}/celebrity")
def celebrity(fid: int, body: dict = Body(...)):
    # No scheduled or background uploads. Consent applies to this exact face crop only.
    if os.getenv("CELEBRITY_MATCHING_ENABLED") != "1":
        raise HTTPException(409, "Connect Amazon Rekognition in the NAS configuration first. Local grouping needs no account.")
    if body.get("consent") != "send-this-crop-to-amazon-rekognition":
        raise HTTPException(400, "Approve sending this face crop to Amazon Rekognition first")
    row = people.face(fid)
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        client = boto3.client("rekognition", region_name=os.getenv("AWS_REGION", "ap-south-1"),
            config=Config(connect_timeout=5, read_timeout=20, retries={"max_attempts": 1}))
        response = client.recognize_celebrities(Image={"Bytes": bytes(row["crop"])})
    except (BotoCoreError, ClientError):
        raise HTTPException(502, "Celebrity lookup failed. Check the NAS's Amazon Rekognition credentials, region and permissions.")
    matches = [{"name": r["Name"], "confidence": round(r.get("MatchConfidence", 0), 1)}
               for r in response.get("CelebrityFaces", []) if r.get("MatchConfidence", 0) >= 95]
    return {"suggestions": sorted(matches, key=lambda r: -r["confidence"]), "provider": "Amazon Rekognition",
            "review_required": True}
