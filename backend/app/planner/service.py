from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from ..explain import template
from ..models import LatLng, Plan, PlanBundle, PlanDiff, RejectedResource, Strategy, UserConstraints
from ..store import store
from .filters import apply_filters
from .graph import build_plan_graph, build_travel_graph
from .search import local_time, search
from .timeline import build_timeline


def make_plan(uc: UserConstraints, now: datetime | None = None, origin: LatLng | None = None,
              explanation: str = "", strategy: Strategy = "recommended") -> Plan:
    uc = uc.model_copy(deep=True)
    now = local_time(now or datetime.now(ZoneInfo("America/New_York"))).replace(second=0, microsecond=0)
    origin = origin or uc.constraints.current_location or store.default_origin
    uc.constraints.current_location = origin
    uc.constraints.start_time = now

    filtered = apply_filters(store.all_resources(), uc)
    travel_graph = build_travel_graph(origin, filtered.eligible, uc, store.transit)
    result = search(travel_graph, filtered.eligible, uc, now, filtered.warnings,
                    filtered.penalties, store.transit, strategy)
    selected = [visit.resource.id for visit in result.visits]
    legs = [
        (visit.from_node, visit.resource.id, visit.leg.route_name or visit.leg.mode)
        for visit in result.visits if visit.leg
    ]
    rejected = list(filtered.rejected)
    for resource_id, reason in result.rejections.items():
        resource = store.get(resource_id)
        if resource and resource_id not in selected:
            rejected.append(RejectedResource(
                resource_id=resource_id, name=resource.name, service=resource.service, reason=reason,
            ))

    return Plan(
        plan_id=str(uuid.uuid4()),
        strategy=strategy,
        created_at=datetime.now().isoformat(timespec="seconds"),
        now=now.isoformat(timespec="minutes"),
        constraints=uc,
        steps=build_timeline(result, now),
        resource_ids=selected,
        total_cost_usd=result.total_cost,
        total_travel_min=result.total_travel_min,
        score=result.score,
        feasible=result.feasible,
        unmet_needs=result.unmet,
        explanation=explanation,
        rejected=rejected,
        graph=build_plan_graph(uc, filtered.eligible, rejected, selected, legs, store.resources),
    )


def diff_plans(old: Plan, new: Plan, trigger: str | None = None) -> PlanDiff:
    old_ids, new_ids = set(old.resource_ids), set(new.resource_ids)
    return PlanDiff(
        removed_resource_ids=[rid for rid in old.resource_ids if rid not in new_ids],
        added_resource_ids=[rid for rid in new.resource_ids if rid not in old_ids],
        trigger=trigger,
        travel_delta_min=new.total_travel_min - old.total_travel_min,
        cost_delta_usd=round(new.total_cost_usd - old.total_cost_usd, 2),
        feasible=new.feasible,
    )


def make_bundle(uc: UserConstraints, now: datetime | None = None,
                previous_plan_id: str | None = None) -> PlanBundle:
    now = now or datetime.now(ZoneInfo("America/New_York"))
    plans: list[Plan] = []
    signatures = set()
    skipped = []
    strategies: tuple[Strategy, ...] = ("recommended", "fastest", "lowest_cost")

    for strategy in strategies:
        plan = make_plan(uc, now, strategy=strategy)
        signature = tuple((step.type, step.resource_id, step.mode, step.time_iso) for step in plan.steps)
        if signature in signatures:
            skipped.append({"fastest": "Fastest", "lowest_cost": "Lowest cost"}.get(strategy, strategy))
            continue
        signatures.add(signature)
        plan.explanation = template(plan)
        no_id = all(not store.resources[rid].eligibility.requires_id for rid in plan.resource_ids)
        condition = "no photo ID needed" if no_id else "photo ID needed at some stops"
        if strategy == "recommended":
            plan.tradeoff = f"Balances travel, cost and intake time; {condition}."
        elif strategy == "fastest":
            saved = plans[0].total_travel_min - plan.total_travel_min
            plan.tradeoff = f"{saved} fewer travel minutes; {condition}."
        else:
            saved = plans[0].total_cost_usd - plan.total_cost_usd
            extra = plan.total_travel_min - plans[0].total_travel_min
            plan.tradeoff = f"Saves ${saved:g}; {abs(extra)} {'more' if extra >= 0 else 'fewer'} travel minutes."
        store.save_plan(plan)
        plans.append(plan)

    note = f"{', '.join(skipped)} produces the same route, so it is shown once. " if skipped else ""
    if len(plans) == 1:
        note += ("Other resources fail the selected requirements, hours, route or budget checks, "
                 "or rank below this route. See checked options.")

    old = store.get_plan(previous_plan_id) if previous_plan_id else None
    diff = None
    if old:
        replacement = next((plan for plan in plans if plan.strategy == old.strategy), plans[0])
        changed = [store.resources[rid] for rid in old.resource_ids
                   if rid in store.resources and store.resources[rid].status.value != "available"]
        trigger = "; ".join(f"{resource.name} is now {resource.status.value}" for resource in changed)
        diff = diff_plans(old, replacement, trigger or "Availability was updated")
    return PlanBundle(plans=plans, alternatives_note=note, diff=diff)
