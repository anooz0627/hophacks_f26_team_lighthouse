from datetime import datetime

import pytest

from app.extraction.fallback import extract
from app.models import ResourceStatus, ServiceType
from app.planner.service import make_plan
from app.store import store

FRI_6PM = datetime(2026, 9, 18, 18, 0)
SCENARIO = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight. I haven't eaten."


@pytest.fixture(autouse=True)
def baltimore():
    store.load("baltimore")
    yield
    store.load("demo")


def test_every_resource_is_sourced():
    for r in store.all_resources():
        assert r.simulated is False, r.id
        assert r.source_url and r.source_url.startswith("http"), r.id
        assert r.last_verified, r.id
        assert r.phone, r.id


def test_19yo_gets_shelter_with_dinner_and_calls_coordinated_entry():
    plan = make_plan(extract(SCENARIO), FRI_6PM)
    assert plan.feasible
    assert plan.resource_ids[0] == "whrc"
    assert plan.steps[0].type == "call" and "Coordinated Entry" in plan.steps[0].title
    assert any(s.type == "note" and "Dinner" in s.title for s in plan.steps)
    reasons = {r.resource_id: r.reason for r in plan.rejected}
    assert reasons["helping_up_mission"] == "minimum age 21"
    assert reasons["sarahs_hope"] == "families with children only"
    assert "baltimore_rescue_mission" not in reasons


def test_replan_when_whrc_full_moves_to_rescue_mission():
    uc = extract(SCENARIO)
    store.set_status("whrc", ResourceStatus.full)
    plan = make_plan(uc, FRI_6PM)
    assert "baltimore_rescue_mission" in plan.resource_ids
    shelter = next(s for s in plan.steps if s.resource_id == "baltimore_rescue_mission" and s.type == "visit")
    assert shelter.time <= "19:45"


def test_rescue_mission_intake_deadline_enforced():
    store.set_status("whrc", ResourceStatus.full)
    plan = make_plan(extract(SCENARIO), datetime(2026, 9, 18, 19, 40))
    assert "baltimore_rescue_mission" not in plan.resource_ids
    assert ServiceType.emergency_housing in plan.unmet_needs


def test_family_goes_to_sarahs_hope():
    uc = extract("Me and my two kids got evicted this morning. I have my ID and about $25 but no car.")
    plan = make_plan(uc, FRI_6PM)
    assert plan.resource_ids[0] == "sarahs_hope"
    assert plan.feasible


def test_long_term_scheduled_on_next_weekday():
    plan = make_plan(extract(SCENARIO), FRI_6PM)
    later = [s for s in plan.steps if s.type == "visit" and s.day_label in ("tomorrow", "later")]
    assert later and later[0].resource_id in ("mohs_coordinated_entry", "hchmd_downtown", "yes_dropin")
