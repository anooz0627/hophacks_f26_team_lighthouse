from datetime import datetime

from app.models import Constraints, Need, ResourceStatus, ServiceType, UserConstraints
from app.planner.service import make_plan
from app.store import store

NOW = datetime(2026, 9, 16, 18, 0)  # Wednesday


def demo_uc() -> UserConstraints:
    return UserConstraints(
        needs=[Need(type=ServiceType.emergency_housing), Need(type=ServiceType.food),
               Need(type=ServiceType.long_term_assistance, priority="low", deadline="tomorrow")],
        constraints=Constraints(age=19, budget_usd=10, has_car=False))


def visits(plan):
    return [s for s in plan.steps if s.type == "visit"]


def test_demo_plan_picks_harbor_light_and_kitchen():
    plan = make_plan(demo_uc(), NOW)
    assert plan.feasible
    assert plan.resource_ids[:2] == ["kitchen_st_vincent", "shelter_harbor_light"]
    assert plan.total_cost_usd <= 10
    assert plan.steps[0].type == "call"
    v = visits(plan)
    shelter = next(s for s in v if s.resource_id == "shelter_harbor_light")
    assert shelter.time < "20:00"  # before intake deadline
    assert "Photo ID" in shelter.bring
    assert any(s.day_label == "tomorrow" for s in v)


def test_replan_when_shelter_full():
    plan1 = make_plan(demo_uc(), NOW)
    store.set_status("shelter_harbor_light", ResourceStatus.full)
    plan2 = make_plan(demo_uc(), NOW)
    assert "shelter_harbor_light" not in plan2.resource_ids
    assert "shelter_eastside" in plan2.resource_ids
    assert any(r.resource_id == "shelter_harbor_light" and r.reason == "currently full" for r in plan2.rejected)
    assert plan1.resource_ids != plan2.resource_ids


def test_rejections_explain_time_constraints():
    plan = make_plan(demo_uc(), NOW)
    reasons = {r.resource_id: r.reason for r in plan.rejected}
    assert reasons["shelter_lombard"].startswith("intake closes 17:00")
    assert reasons["shelter_northern"] == "minimum age 21"


def test_arrival_after_intake_is_not_recommended():
    # at 19:50 there is no way to eat and still reach Harbor Light by 20:00
    plan = make_plan(demo_uc(), datetime(2026, 9, 16, 19, 50))
    assert "shelter_harbor_light" not in plan.resource_ids
    # Food cannot be reached before service ends; label the surviving shelter plan partial.
    assert not plan.feasible
    assert ServiceType.food in plan.unmet_needs


def test_zero_budget_uses_walking_only():
    uc = demo_uc()
    uc.constraints.budget_usd = 0
    plan = make_plan(uc, NOW)
    assert plan.feasible
    assert plan.total_cost_usd == 0
    assert all(s.mode != "bus" for s in plan.steps if s.type == "travel" and s.day_label == "tonight")


def test_infeasible_when_everything_full():
    for r in store.all_resources():
        if r.service == ServiceType.emergency_housing:
            store.set_status(r.id, ResourceStatus.full)
    plan = make_plan(demo_uc(), NOW)
    assert ServiceType.emergency_housing in plan.unmet_needs
    assert any(s.type == "note" for s in plan.steps)
    # still schedules food
    assert "kitchen_st_vincent" in plan.resource_ids


def test_graph_marks_selected_nodes():
    plan = make_plan(demo_uc(), NOW)
    sel = {n.id for n in plan.graph.nodes if n.selected and n.kind == "resource"}
    assert sel == set(plan.resource_ids)


def test_unknown_budget_prefers_free_shelter():
    uc = demo_uc()
    uc.constraints.budget_usd = None
    uc.constraints.age = 30
    plan = make_plan(uc, NOW)
    assert "hostel_lowcost" not in plan.resource_ids


def test_tomorrow_prefers_housing_center_when_id_known():
    plan = make_plan(demo_uc(), NOW)
    tomorrow = [s for s in plan.steps if s.type == "visit" and s.day_label == "tomorrow"]
    assert tomorrow and tomorrow[0].resource_id == "housing_resource_center"


def test_tomorrow_prefers_id_clinic_when_no_id():
    uc = demo_uc()
    uc.constraints.has_id = False
    plan = make_plan(uc, datetime(2026, 9, 17, 18, 0))  # Thu -> clinic open Fri
    tomorrow = [s for s in plan.steps if s.type == "visit" and s.day_label == "tomorrow"]
    assert tomorrow and tomorrow[0].resource_id == "id_clinic"
