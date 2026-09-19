import os

os.environ["AIDGRAPH_DISABLE_LLM"] = "1"

from fastapi.testclient import TestClient

from app.main import app

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

    r = client.post("/replan", json={"plan_id": plan["plan_id"]})
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
