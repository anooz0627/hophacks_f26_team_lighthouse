import os
from datetime import datetime

import pytest

os.environ["AIDGRAPH_DISABLE_LLM"] = "1"

from fastapi.testclient import TestClient

from app.main import app
from app.extraction.fallback import extract
from app.planner.service import make_plan
from app.store import store

client = TestClient(app)
TEXT = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight. I haven't eaten."
NOW = "2026-09-16T18:00:00"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_plan_and_replan_flow():
    r = client.post("/plan", json={"text": TEXT, "now": NOW})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["feasible"] and "shelter_harbor_light" in plan["resource_ids"]
    assert plan["explanation"]

    r = client.patch("/resources/shelter_harbor_light/status", json={"status": "full"})
    assert r.status_code == 200 and r.json()["status"] == "full"

    r = client.post("/replan", json={"plan_id": plan["plan_id"], "now": NOW})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["previous_plan_id"] == plan["plan_id"]
    assert "shelter_harbor_light" in body["diff"]["removed_resource_ids"]
    assert "shelter_eastside" in body["diff"]["added_resource_ids"]
    assert "full" in body["diff"]["trigger"]

    r = client.post("/resources/reset")
    assert r.status_code == 200
    assert next(x for x in r.json() if x["id"] == "shelter_harbor_light")["status"] == "available"


def test_plan_accepts_timezone_aware_now():
    r = client.post("/plan", json={"text": TEXT, "now": "2026-09-16T18:00:00-04:00"})
    assert r.status_code == 200, r.text


def test_replan_unknown_plan_404():
    assert client.post("/replan", json={"plan_id": "nope"}).status_code == 404


@pytest.mark.parametrize("strategy", ["fastest", "lowest_cost"])
def test_replan_keeps_selected_strategy(strategy):
    old = make_plan(extract(TEXT), datetime.fromisoformat(NOW), strategy=strategy)
    store.save_plan(old)

    response = client.post("/replan", json={"plan_id": old.plan_id, "now": NOW})

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["strategy"] == strategy
    assert body["plan"]["now"] == old.now
    assert body["plan"]["resource_ids"] == old.resource_ids
    assert body["diff"]["travel_delta_min"] == 0
    assert body["diff"]["cost_delta_usd"] == 0


@pytest.mark.parametrize("endpoint", ["/plans", "/plan/from-constraints"])
@pytest.mark.parametrize(("needs", "message"), [
    ([], "Select at least one service need"),
    ([{"type": "food", "deadline": "custom"}], "Add a custom deadline"),
])
def test_reviewed_plan_rejects_incomplete_constraints(endpoint, needs, message):
    constraints = {"needs": needs, "constraints": {}}
    body = {"constraints": constraints, "now": NOW} if endpoint == "/plans" else constraints

    response = client.post(endpoint, json=body)

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert not store.plans
