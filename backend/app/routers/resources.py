from fastapi import APIRouter, HTTPException

from ..models import Resource, StatusUpdate
from ..store import store

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=list[Resource])
def list_resources() -> list[Resource]:
    return store.all_resources()


@router.post("/reset", response_model=list[Resource])
def reset_resources() -> list[Resource]:
    store.reset_status()
    return store.all_resources()


@router.get("/{resource_id}", response_model=Resource)
def get_resource(resource_id: str) -> Resource:
    r = store.get(resource_id)
    if not r:
        raise HTTPException(404, "resource not found")
    return r


@router.patch("/{resource_id}/status", response_model=Resource)
def set_status(resource_id: str, body: StatusUpdate) -> Resource:
    if not store.get(resource_id):
        raise HTTPException(404, "resource not found")
    return store.set_status(resource_id, body.status, body.capacity)
