import os

os.environ["LIGHTHOUSE_DISABLE_LLM"] = "1"

from datetime import datetime

from fastapi.testclient import TestClient

from app.extraction.fallback import extract
from app.main import app
from app.models import ServiceType
from app.planner.service import make_plan
from app.store import store

client = TestClient(app)
NOW = datetime(2026, 9, 17, 18)
SCENARIO = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight."


def test_feasible_plan_has_no_blocked_needs():
    plan = make_plan(extract(SCENARIO), NOW)
    assert plan.feasible and plan.blocked == []


def test_walking_limit_blocks_with_a_route_diagnosis():
    uc = extract(SCENARIO)
    uc.constraints.transport = "walking"
    uc.constraints.max_walk_km = 0.3
    plan = make_plan(uc, NOW)
    assert not plan.feasible
    causes = {b.need: b for b in plan.blocked}
    assert ServiceType.emergency_housing in causes
    b = causes[ServiceType.emergency_housing]
    assert b.cause == "route" and "walking limit" in b.summary and "bus or rideshare" in b.suggestion
    assert b.checked > 0


def test_fees_over_budget_block_longer_term_help():
    for r in store.all_resources():
        if r.service == ServiceType.long_term_assistance:
            r.cost = 11
    plan = make_plan(extract(SCENARIO), NOW)
    b = next(x for x in plan.blocked if x.need == ServiceType.long_term_assistance)
    assert b.cause == "budget" and "exceed your budget" in b.summary


def test_all_full_blocks_with_status_and_shows_up_in_speech():
    from app.models import ResourceStatus
    from app.voice import speech_script
    for r in store.all_resources():
        if r.service == ServiceType.emergency_housing:
            store.set_status(r.id, ResourceStatus.full)
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    b = next(x for x in plan["blocked"] if x["need"] == "emergency_housing")
    assert b["cause"] == "status"
    from app.models import Plan
    assert b["summary"] in speech_script(Plan.model_validate(plan))


def test_missing_id_points_to_an_id_replacement_helper_when_the_data_has_one():
    from app.models import ResourceStatus
    uc = extract(SCENARIO)
    uc.constraints.has_id = False
    for r in store.all_resources():
        if r.service == ServiceType.emergency_housing and not r.eligibility.requires_id:
            store.set_status(r.id, ResourceStatus.closed)
    plan = make_plan(uc, NOW)
    b = next((x for x in plan.blocked if x.need == ServiceType.emergency_housing), None)
    assert b is not None
    helper = next((r for r in store.all_resources() if "id_replacement" in r.tags), None)
    if b.cause == "id" and helper:
        assert b.first_step_resource_id == helper.id and helper.name in b.suggestion
