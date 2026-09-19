from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import explain
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
    plan = make_plan(body, now=now)
    plan.explanation = explain.summarize(plan)
    store.save_plan(plan)
    return plan


@router.post("/replan", response_model=ReplanResponse)
def replan(body: ReplanRequest) -> ReplanResponse:
    old = store.get_plan(body.plan_id)
    if not old:
        raise HTTPException(404, "plan not found")
    now = body.now or datetime.fromisoformat(old.now)
    uc = old.constraints.model_copy(deep=True)
    new = make_plan(uc, now=now, origin=uc.constraints.current_location)
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
    if not body.constraints.needs:
        raise HTTPException(422, "Select at least one service need to build a plan.")
    if any(n.deadline == "custom" for n in body.constraints.needs) and not body.constraints.constraints.custom_deadline:
        raise HTTPException(422, "Add a custom deadline or choose another deadline.")
    return make_bundle(body.constraints, body.now, body.previous_plan_id)
