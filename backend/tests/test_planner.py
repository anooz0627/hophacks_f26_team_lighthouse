from datetime import datetime

from app.models import Constraints, Need, ResourceStatus, ServiceType, UserConstraints
from app.planner.service import make_bundle, make_plan
from app.store import store

NOW = datetime(2026, 9, 16, 18)


def demo_constraints() -> UserConstraints:
    return UserConstraints(
        needs=[
            Need(type=ServiceType.emergency_housing),
            Need(type=ServiceType.food),
            Need(type=ServiceType.long_term_assistance, priority="low", deadline="tomorrow"),
        ],
        constraints=Constraints(age=19, budget_usd=10, has_car=False),
    )


def test_demo_plan_fits_budget_and_intake():
    plan = make_plan(demo_constraints(), NOW)

    assert plan.feasible
    assert not plan.unmet_needs
    assert plan.resource_ids[:2] == ["kitchen_st_vincent", "shelter_harbor_light"]
    assert plan.total_cost_usd <= 10
    assert plan.total_cost_usd == sum(step.cost_usd for step in plan.steps)
    assert plan.steps[0].type == "call"
    assert [step.time_iso for step in plan.steps] == sorted(step.time_iso for step in plan.steps)

    visits = [step for step in plan.steps if step.type == "visit"]
    shelter = next(step for step in visits if step.resource_id == "shelter_harbor_light")
    assert datetime.fromisoformat(shelter.time_iso) <= NOW.replace(hour=20)
    assert "Photo ID" in shelter.bring
    assert any(step.day_label == "tomorrow" for step in visits)


def test_full_shelter_is_replaced_in_replan():
    constraints = demo_constraints()
    old = make_bundle(constraints, NOW).plans[0]
    assert "shelter_harbor_light" in old.resource_ids

    store.set_status("shelter_harbor_light", ResourceStatus.full)
    bundle = make_bundle(constraints, NOW, previous_plan_id=old.plan_id)
    new = bundle.plans[0]

    assert new.feasible
    assert "shelter_eastside" in new.resource_ids
    assert all("shelter_harbor_light" not in plan.resource_ids for plan in bundle.plans)
    assert bundle.diff is not None
    assert "shelter_harbor_light" in bundle.diff.removed_resource_ids
    assert "shelter_eastside" in bundle.diff.added_resource_ids
    assert "full" in bundle.diff.trigger
    assert bundle.diff.travel_delta_min == new.total_travel_min - old.total_travel_min
    assert bundle.diff.cost_delta_usd == round(new.total_cost_usd - old.total_cost_usd, 2)


def test_rejected_shelter_explains_intake_cutoff():
    plan = make_plan(demo_constraints(), NOW)
    reasons = {resource.resource_id: resource.reason for resource in plan.rejected}

    assert "shelter_lombard" not in plan.resource_ids
    assert reasons["shelter_lombard"].startswith("intake closes 17:00")


def test_late_start_returns_partial_plan():
    plan = make_plan(demo_constraints(), NOW.replace(hour=19, minute=50))

    assert "shelter_harbor_light" not in plan.resource_ids
    assert not plan.feasible
    assert ServiceType.food in plan.unmet_needs
    assert any(step.type == "note" for step in plan.steps)
