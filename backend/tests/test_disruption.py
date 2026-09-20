import os

os.environ["LIGHTHOUSE_DISABLE_LLM"] = "1"

from datetime import datetime

from fastapi.testclient import TestClient

from app import agent
from app.agent import parse_rules
from app.extraction.fallback import extract
from app.main import app
from app.models import Progress, ServiceType
from app.planner.service import make_bundle, make_plan
from app.planner.travel import travel_options
from app.store import store

client = TestClient(app)
NOW = datetime(2026, 9, 17, 18)
SCENARIO = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight. I haven't eaten."


def demo_plan():
    plan = make_plan(extract(SCENARIO), NOW)
    store.save_plan(plan)
    return plan


def names(calls):
    return [c.name for c in calls]


def test_rules_parse_lateness_and_missed_bus():
    plan = demo_plan()
    assert parse_rules("I'm running 25 minutes late", plan)[0].args["minutes"] == 25
    assert parse_rules("I missed the bus", plan)[0].args == {"minutes": agent.DEFAULT_MISSED_BUS_MIN}
    assert parse_rules("Sorry, running late", plan)[0].args == {"minutes": agent.DEFAULT_LATE_MIN}


def test_rules_parse_status_delay_and_constraints():
    plan = demo_plan()
    shelter = next(rid for rid in plan.resource_ids if store.get(rid).service == ServiceType.emergency_housing)
    calls = parse_rules(f"{store.get(shelter).name} is full", plan)
    assert calls[0].name == "mark_resource_status" and calls[0].args == {"resource_id": shelter, "status": "full"}
    calls = parse_rules("They said no beds tonight", plan)
    assert calls[0].args["resource_id"] == shelter
    calls = parse_rules("the bus is delayed by 12 minutes", plan)
    assert names(calls) == ["report_transit_delay"] and calls[0].args["minutes"] == 12
    calls = parse_rules("I lost my wallet and only have $3 now, and I hurt my knee", plan)
    assert [(c.args["field"], c.args["value"]) for c in calls] == [("has_id", "false"), ("budget_usd", "3"), ("limited_walking", "true")]
    calls = parse_rules("I'm at Mount Vernon now", plan)
    assert calls[0].name == "set_location" and "Mount Vernon" in calls[0].args["place"]
    assert parse_rules("Thanks, all good", plan) == []


def test_bus_delay_changes_travel_time_and_is_described():
    a, b = (39.291, -76.6215), (39.31, -76.579)
    before = {leg.route_id: leg.duration_min for leg in travel_options(a, b, extract(SCENARIO).constraints, store.transit) if leg.mode == "bus"}
    assert before
    route_id = next(iter(before))
    store.set_delay(route_id, 10)
    after = {leg.route_id: leg for leg in travel_options(a, b, extract(SCENARIO).constraints, store.transit) if leg.mode == "bus"}
    assert after[route_id].duration_min == before[route_id] + 10
    assert "delayed 10 min" in after[route_id].describe()
    store.reset_delays()
    assert all(r.delay_min == 0 for r in store.transit.routes)


def test_progress_replans_from_where_the_person_is():
    plan = demo_plan()
    food_visit = next(s for s in plan.steps if s.type == "visit" and store.get(s.resource_id).service == ServiceType.food)
    progress = Progress(completed_orders=[s.order for s in plan.steps if s.order <= food_visit.order], now=food_visit.time_iso)
    bundle = make_bundle(plan.constraints, previous_plan_id=plan.plan_id, progress=progress)
    new = bundle.plans[0]
    assert ServiceType.food not in {n.type for n in new.constraints.needs}
    assert food_visit.resource_id not in new.resource_ids
    kitchen = store.get(food_visit.resource_id)
    assert new.constraints.constraints.current_location.lat == kitchen.lat
    assert new.steps[0].time_iso >= food_visit.time_iso


def test_disruption_endpoint_shifts_time_and_replaces_full_shelter():
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    shelter = next(rid for rid in plan["resource_ids"] if store.get(rid).service == ServiceType.emergency_housing)
    r = client.post("/agent/disruption", json={"plan_id": plan["plan_id"], "text": f"I missed the bus and {store.get(shelter).name} says they are full"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "rules" and len(body["actions"]) == 2
    assert shelter in body["diff"]["removed_resource_ids"]
    assert "behind" in body["diff"]["trigger"] and "full" in body["diff"]["trigger"]
    assert body["plans"][0]["feasible"]
    assert body["plans"][0]["steps"][0]["time"] == "18:15"
    assert "Got it" in body["message"] and store.get(shelter).name in body["message"]


def test_disruption_with_no_change_keeps_plan():
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    body = client.post("/agent/disruption", json={"plan_id": plan["plan_id"], "text": "okay thanks"}).json()
    assert body["actions"] == []
    assert body["plans"][0]["resource_ids"] == plan["resource_ids"]
    assert "still stand" in body["message"]
    assert client.post("/agent/disruption", json={"plan_id": "nope", "text": "late"}).status_code == 404


def test_transit_delay_endpoints_and_reset():
    routes = client.get("/transit").json()
    rid = routes[0]["id"]
    assert client.patch(f"/transit/{rid}/delay", json={"delay_min": 20}).json()["delay_min"] == 20
    assert client.patch("/transit/nope/delay", json={"delay_min": 5}).status_code == 404
    assert client.patch(f"/transit/{rid}/delay", json={"delay_min": 999}).status_code == 422
    client.post("/resources/reset")
    assert next(r for r in client.get("/transit").json() if r["id"] == rid)["delay_min"] == 0


def test_long_walks_are_allowed_but_flagged_and_capped():
    from app.models import Constraints
    a = (39.291, -76.6215)
    five_km = (39.336, -76.6215)
    nine_km = (39.372, -76.6215)
    legs = travel_options(a, five_km, Constraints(transport="walking"), store.transit)
    assert legs and legs[0].long_walk and "long walk" in legs[0].describe()
    assert not travel_options(a, nine_km, Constraints(transport="walking"), store.transit)
    assert not travel_options(a, five_km, Constraints(transport="walking", max_walk_km=3), store.transit)
    short = travel_options(a, (39.30, -76.6215), Constraints(transport="walking"), store.transit)
    assert short and not short[0].long_walk


def test_far_start_gets_a_plan_with_a_long_walk_warning_and_too_far_shortens_it():
    from app.models import LatLng
    uc = extract(SCENARIO)
    uc.constraints.transport = "walking"
    uc.constraints.current_location = LatLng(lat=39.335, lng=-76.62)
    plan = make_plan(uc, NOW, origin=uc.constraints.current_location)
    store.save_plan(plan)
    assert plan.resource_ids
    warnings = [w for s in plan.steps for w in s.warnings]
    assert any(w.startswith("Long walk") for w in warnings)
    calls = parse_rules("that's too far for me", plan)
    assert calls[0].args == {"field": "max_walk_km", "value": "3"}
    body = client.post("/agent/disruption", json={"plan_id": plan.plan_id, "text": "that's too far for me"}).json()
    assert "Walking limit set to 3 km" in body["actions"]
    new = body["plans"][0]
    assert not new["resource_ids"] or all(
        s["type"] != "travel" or "long walk" not in s["detail"] for s in new["steps"])


def test_agent_message_acknowledges_completed_steps():
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    food_visit = next(s for s in plan["steps"] if s["type"] == "visit" and store.get(s["resource_id"]).service == ServiceType.food)
    done = [s["order"] for s in plan["steps"] if s["order"] <= food_visit["order"]]
    body = client.post("/agent/disruption", json={"plan_id": plan["plan_id"], "text": "I'm running 10 minutes late",
                                                  "progress": {"completed_orders": done}}).json()
    kitchen = store.get(food_visit["resource_id"]).name
    assert f"continuing from {kitchen}" in body["message"]
    assert food_visit["resource_id"] not in body["plans"][0]["resource_ids"]
    assert body["plans"][0]["steps"][0]["time"] >= food_visit["time"]


def test_finished_shelter_with_dinner_covers_food_and_is_not_reported_as_removed():
    store.load("baltimore")
    plan = client.post("/plan", json={"text": SCENARIO, "now": "2026-09-20T18:00:00"}).json()
    checkin = next(s for s in plan["steps"] if s["type"] == "visit" and store.get(s["resource_id"]).service == ServiceType.emergency_housing)
    assert any(s["type"] == "note" and "Dinner" in s["title"] for s in plan["steps"])
    done = [s["order"] for s in plan["steps"] if s["order"] <= checkin["order"]]
    body = client.post("/agent/disruption", json={"plan_id": plan["plan_id"], "text": "running 20 minutes late",
                                                  "progress": {"completed_orders": done}}).json()
    new = body["plans"][0]
    assert ServiceType.food.value not in [n["type"] for n in new["constraints"]["needs"]]
    assert all(store.get(rid).service != ServiceType.food for rid in new["resource_ids"])
    assert checkin["resource_id"] not in body["diff"]["removed_resource_ids"]
    assert "no longer fits" not in body["message"]
    assert "continuing from" in body["message"]
    store.load("demo")
