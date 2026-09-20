from datetime import datetime

import pytest

from app.explain import template
from app.extraction.fallback import extract
from app.models import LatLng, ResourceStatus
from app.planner.service import make_plan
from app.store import store
from app.voice import speech_script

TEXT = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight."


@pytest.mark.parametrize("hour", [1, 18])
def test_far_gps_gets_a_long_walk_plan_and_a_walk_limit_turns_it_into_contacts(hour):
    store.load("baltimore")
    uc = extract(TEXT)
    now = datetime(2026, 9, 20, hour)
    before = make_plan(uc, now, origin=LatLng(lat=39.291, lng=-76.6215))
    assert before.feasible
    assert before.resource_ids
    assert not before.unrouted_resources
    assert not any(w.startswith("Long walk") for s in before.steps for w in s.warnings)
    gps = LatLng(lat=39.329, lng=-76.620)
    after = make_plan(uc, now, origin=gps)
    assert after.constraints.constraints.current_location == gps
    assert after.feasible and "whrc" in after.resource_ids
    assert not after.unrouted_resources
    assert any(s.type == "travel" and s.mode == "bus" for s in after.steps)
    uc.constraints.transport = "walking"
    on_foot = make_plan(uc, now, origin=gps)
    assert on_foot.feasible and "whrc" in on_foot.resource_ids
    assert any(w.startswith("Long walk") for s in on_foot.steps for w in s.warnings)
    uc.constraints.max_walk_km = 3
    limited = make_plan(uc, now, origin=gps)
    assert not limited.feasible
    assert not limited.resource_ids
    assert limited.unmet_needs
    assert "whrc" in {r.resource_id for r in limited.unrouted_resources}
    assert all(r.reason and r.distance_km > 0 for r in limited.unrouted_resources)
    assert not any(s.type == "travel" for s in limited.steps)
    assert "route is not confirmed" in template(limited)
    assert "A route is not confirmed" in speech_script(limited)


def test_contacts_still_obey_age_availability_and_accessibility():
    store.load("baltimore")
    uc = extract(TEXT)
    uc.constraints.current_location = LatLng(lat=39.329, lng=-76.620)
    uc.constraints.transport = "walking"
    uc.constraints.max_walk_km = 3
    store.set_status("whrc", ResourceStatus.full)
    plan = make_plan(uc, datetime(2026, 9, 20, 1))
    ids = {item.resource_id for item in plan.unrouted_resources}
    assert "whrc" not in ids
    for rid in ids:
        resource = store.get(rid)
        assert resource.eligibility.min_age is None or resource.eligibility.min_age <= 19
    uc.constraints.accessibility = ["step_free"]
    accessible = make_plan(uc, datetime(2026, 9, 20, 1))
    assert all("step_free" in store.get(item.resource_id).eligibility.accessibility for item in accessible.unrouted_resources)


def test_unknown_requirements_are_retained_for_unrouted_contacts():
    store.load("baltimore")
    uc = extract(TEXT)
    uc.constraints.age = None
    uc.constraints.transport = "walking"
    uc.constraints.max_walk_km = 3
    plan = make_plan(uc, datetime(2026, 9, 20, 1), origin=LatLng(lat=39.329, lng=-76.620))
    assert any("Age requirement" in warning for item in plan.unrouted_resources for warning in item.warnings)
