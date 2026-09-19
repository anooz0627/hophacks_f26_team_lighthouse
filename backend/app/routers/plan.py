from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import explain
from ..extraction import extract as extraction
from ..models import (
    ExtractRequest, Plan, PlanBundle, PlanBundleRequest, PlanRequest,
    ReplanRequest, ReplanResponse, UserConstraints,
)
from ..planner.service import diff_plans, make_bundle, make_plan
from ..store import store

router = APIRouter(tags=["plan"])


def extract_constraints(text: str) -> UserConstraints:
    try:
        return extraction.extract(text)
    except ValidationError as exc:
        raise HTTPException(
            422, "Check the situation's values: age must be 0–120, budget $0–$100,000, and household size 1–20.",
        ) from exc


@router.post("/extract", response_model=UserConstraints)
def extract(body: ExtractRequest) -> UserConstraints:
    return extract_constraints(body.text)


@router.post("/plan", response_model=Plan)
def create_plan(body: PlanRequest) -> Plan:
    constraints = extract_constraints(body.text)
    plan = make_plan(constraints, now=body.now, origin=body.current_location)
    plan.explanation = explain.summarize(plan)
    store.save_plan(plan)
    return plan


@router.post("/plan/from-constraints", response_model=Plan)
def plan_from_constraints(body: UserConstraints, now: datetime | None = None) -> Plan:
    plan = make_plan(body, now=now)
    plan.explanation = explain.summarize(plan)
    store.save_plan(plan)
    return plan


@router.post("/replan", response_model=ReplanResponse)
def replan(body: ReplanRequest) -> ReplanResponse:
    old = store.get_plan(body.plan_id)
    if old is None:
        raise HTTPException(404, "plan not found")
    now = body.now or datetime.fromisoformat(old.now)
    constraints = old.constraints.model_copy(deep=True)
    new = make_plan(constraints, now=now, origin=constraints.constraints.current_location)
    new.explanation = explain.summarize(new)
    store.save_plan(new)
    diff = diff_plans(old, new)
    for resource_id in diff.removed_resource_ids:
        resource = store.get(resource_id)
        if resource and resource.status.value != "available":
            diff.trigger = f"{resource.name} is now {resource.status.value}"
            break
    return ReplanResponse(plan=new, previous_plan_id=old.plan_id, diff=diff)


@router.post("/plans", response_model=PlanBundle)
def plan_strategies(body: PlanBundleRequest) -> PlanBundle:
    if not body.constraints.needs:
        raise HTTPException(422, "Select at least one service need to build a plan.")
    custom_deadline = body.constraints.constraints.custom_deadline
    if any(need.deadline == "custom" for need in body.constraints.needs) and not custom_deadline:
        raise HTTPException(422, "Add a custom deadline or choose another deadline.")
    return make_bundle(body.constraints, body.now, body.previous_plan_id)
