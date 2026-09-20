from fastapi import APIRouter, HTTPException

from .. import agent
from ..models import DisruptionRequest, DisruptionResponse, TransitDelayUpdate, TransitRoute
from ..store import store

router = APIRouter(tags=["agent"])


@router.post("/agent/disruption", response_model=DisruptionResponse)
def disruption(body: DisruptionRequest) -> DisruptionResponse:
    try:
        return agent.handle(body.plan_id, body.text, body.progress)
    except KeyError:
        raise HTTPException(404, "plan not found") from None


@router.get("/transit", response_model=list[TransitRoute])
def list_routes() -> list[TransitRoute]:
    return store.transit.routes


@router.patch("/transit/{route_id}/delay", response_model=TransitRoute)
def set_delay(route_id: str, body: TransitDelayUpdate) -> TransitRoute:
    try:
        return store.set_delay(route_id, body.delay_min)
    except KeyError:
        raise HTTPException(404, "route not found") from None
