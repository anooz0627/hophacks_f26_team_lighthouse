from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.extraction.fallback import extract
from app.main import app
from app.models import Constraints, Eligibility, LatLng, Resource, ServiceType
from app.planner import service
from app.planner.filters import apply_filters
from app.store import store

client = TestClient(app)
TEXT = "I need food tonight and can only walk."


def clock_at(monkeypatch, iso):
    instant = datetime.fromisoformat(iso)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(service, "datetime", Clock)
    return instant.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None).isoformat(timespec="minutes")


def test_plan_and_replan_use_request_time_and_preserve_origin(monkeypatch):
    uc = extract(TEXT)
    uc.constraints.current_location = LatLng(lat=39.30, lng=-76.61)
    uc.constraints.location_label = "Current location"
    first_now = clock_at(monkeypatch, "2026-09-21T03:58:00+00:00")
    first = client.post("/plans", json={"constraints": uc.model_dump(mode="json")}).json()
    assert {plan["now"] for plan in first["plans"]} == {first_now}
    plan = first["plans"][0]
    assert plan["constraints"]["constraints"]["current_location"] == {"lat": 39.30, "lng": -76.61}
    next_now = clock_at(monkeypatch, "2026-09-21T04:02:00+00:00")
    revised = client.post("/replan", json={"plan_id": plan["plan_id"]})
    assert revised.status_code == 200
    assert revised.json()["plan"]["now"] == next_now == "2026-09-21T00:02"
    assert store.get_plan(plan["plan_id"]).now == first_now


@pytest.mark.parametrize("gender", ["non_binary", "self_describe", "prefer_not_to_say", None])
def test_unspecified_service_eligibility_requires_confirmation(gender):
    uc = extract(TEXT)
    uc.constraints.gender = gender
    resources = [Resource(id="restricted", name="Restricted service", service=ServiceType.food,
                          hours=[], address="Baltimore", lat=39.29, lng=-76.61, eligibility=Eligibility(gender="female")),
                 Resource(id="open", name="Open service", service=ServiceType.food,
                          hours=[], address="Baltimore", lat=39.29, lng=-76.61)]
    result = apply_filters(resources, uc)
    assert {r.id for r in result.eligible} == {"restricted", "open"}
    assert "confirm eligibility" in result.warnings["restricted"][0]
    assert "open" not in result.warnings


def test_binary_restriction_and_access_requirements_are_preserved():
    uc = extract(TEXT)
    uc.constraints.gender = "male"
    resource = Resource(id="restricted", name="Restricted service", service=ServiceType.food,
                        hours=[], address="Baltimore", lat=39.29, lng=-76.61, eligibility=Eligibility(gender="female"))
    assert apply_filters([resource], uc).rejected[0].reason == "female-only"
    uc.constraints.gender = "non_binary"
    uc.constraints.accessibility = ["step_free"]
    assert "support is not confirmed" in apply_filters([resource], uc).rejected[0].reason


def test_self_description_is_optional_and_length_limited():
    assert Constraints(gender="self_describe", gender_description="Agender").gender_description == "Agender"
    with pytest.raises(ValueError):
        Constraints(gender="self_describe", gender_description="x" * 81)
