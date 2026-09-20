from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError

from .. import explain, voice
from ..extraction import extract as extraction
from ..models import (ExtractRequest, Plan, PlanBundle, PlanBundleRequest, PlanRequest, ReplanRequest,
                      ReplanResponse, UserConstraints)
from ..planner.service import diff_plans, make_bundle, make_plan
from ..store import store

router = APIRouter(tags=["plan"])

INVALID_VALUES = ("Check the situation's values: age must be 0–120, budget $0–$100,000, "
                  "and household size 1–20.")


def extract_constraints(text: str) -> UserConstraints:
    try:
        return extraction.extract(text)
    except ValidationError as exc:
        raise HTTPException(422, INVALID_VALUES) from exc


def validate_constraints(uc: UserConstraints) -> None:
    if not uc.needs:
        raise HTTPException(422, "Select at least one service need to build a plan.")
    if any(need.deadline == "custom" for need in uc.needs) and not uc.constraints.custom_deadline:
        raise HTTPException(422, "Add a custom deadline or choose another deadline.")


@router.post("/extract", response_model=UserConstraints)
def extract(body: ExtractRequest) -> UserConstraints:
    return extract_constraints(body.text)


@router.post("/plan", response_model=Plan)
def create_plan(body: PlanRequest) -> Plan:
    uc = extract_constraints(body.text)
    plan = make_plan(uc, now=body.now, origin=body.current_location)
    plan.explanation = explain.summarize(plan)
    store.save_plan(plan)
    return plan


@router.post("/plan/from-constraints", response_model=Plan)
def plan_from_constraints(body: UserConstraints, now: Optional[datetime] = None) -> Plan:
    validate_constraints(body)
    plan = make_plan(body, now=now)
    plan.explanation = explain.summarize(plan)
    store.save_plan(plan)
    return plan


@router.post("/replan", response_model=ReplanResponse)
def replan(body: ReplanRequest) -> ReplanResponse:
    old = store.get_plan(body.plan_id)
    if not old:
        raise HTTPException(404, "plan not found")
    now = body.now
    uc = old.constraints.model_copy(deep=True)
    new = make_plan(uc, now=now, origin=uc.constraints.current_location, strategy=old.strategy)
    new.explanation = explain.summarize(new)
    store.save_plan(new)
    diff = diff_plans(old, new)
    for rid in diff.removed_resource_ids:
        r = store.get(rid)
        if r and r.status.value != "available":
            diff.trigger = f"{r.name} is now {r.status.value}"
            break
    return ReplanResponse(plan=new, previous_plan_id=old.plan_id, diff=diff)


@router.post("/plans", response_model=PlanBundle)
def plan_strategies(body: PlanBundleRequest) -> PlanBundle:
    validate_constraints(body.constraints)
    return make_bundle(body.constraints, body.now, body.previous_plan_id, body.progress)


def saved_plan(plan_id: str) -> Plan:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise HTTPException(404, "plan not found")
    return plan


@router.get("/plans/{plan_id}/script")
def plan_script(plan_id: str) -> dict[str, str]:
    return {"text": explain.narrate(saved_plan(plan_id))}


@router.get("/plans/{plan_id}/audio")
def plan_audio(plan_id: str) -> Response:
    plan = saved_plan(plan_id)
    if not voice.voice_enabled():
        raise HTTPException(503, "Voice playback is not configured on this server.")
    try:
        data = voice.audio_for(plan.plan_id, explain.narrate(plan))
    except Exception as exc:
        raise HTTPException(502, "Voice playback is temporarily unavailable.") from exc
    return Response(content=data, media_type="audio/mpeg", headers={"cache-control": "private, max-age=600"})
