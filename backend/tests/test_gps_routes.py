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
def test_gps_changes_route_coverage_without_losing_matching_resources(hour):
    store.load("baltimore")
    uc = extract(TEXT)
    now = datetime(2026, 9, 20, hour)
    before = make_plan(uc, now, origin=LatLng(lat=39.291, lng=-76.6215))
    assert before.feasible
    assert before.resource_ids
    assert not before.unrouted_resources
    gps = LatLng(lat=39.329, lng=-76.620)
    after = make_plan(uc, now, origin=gps)
    assert after.constraints.constraints.current_location == gps
    assert not after.feasible
    assert not after.resource_ids
    assert after.unmet_needs
    assert "whrc" in {r.resource_id for r in after.unrouted_resources}
    assert all(r.reason and r.distance_km > 0 for r in after.unrouted_resources)
    assert not any(s.type == "travel" for s in after.steps)
    assert "route is not confirmed" in template(after)
    assert "A route is not confirmed" in speech_script(after)


def test_contacts_still_obey_age_availability_and_accessibility():
    store.load("baltimore")
    uc = extract(TEXT)
    uc.constraints.current_location = LatLng(lat=39.329, lng=-76.620)
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
    plan = make_plan(uc, datetime(2026, 9, 20, 1), origin=LatLng(lat=39.329, lng=-76.620))
    assert any("Age requirement" in warning for item in plan.unrouted_resources for warning in item.warnings)
