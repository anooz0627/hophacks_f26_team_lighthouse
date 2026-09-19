from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..explain import template
from ..models import (LatLng, Plan, PlanBundle, PlanDiff, RejectedResource, Strategy, UserConstraints)
from ..store import store
from .filters import apply_filters
from .graph import build_plan_graph, build_travel_graph
from .search import local_time, search
from .timeline import build_timeline

STRATEGIES: tuple[Strategy, ...] = ("recommended", "fastest", "lowest_cost")
STRATEGY_LABEL = {"fastest": "Fastest", "lowest_cost": "Lowest cost"}


def make_plan(uc: UserConstraints, now: Optional[datetime] = None, origin: Optional[LatLng] = None,
              explanation: str = "", strategy: Strategy = "recommended") -> Plan:
    uc = uc.model_copy(deep=True)
    now = local_time(now or datetime.now(ZoneInfo("America/New_York")))
    now = now.replace(second=0, microsecond=0)
    origin = origin or uc.constraints.current_location or store.default_origin
    uc.constraints.current_location = origin
    uc.constraints.start_time = now

    fr = apply_filters(store.all_resources(), uc)
    g = build_travel_graph(origin, fr.eligible, uc, store.transit)
    result = search(g, fr.eligible, uc, now, fr.warnings, fr.penalties, store.transit, strategy)
    steps = build_timeline(result, now)

    selected = [v.resource.id for v in result.visits]
    legs = []
    for v in result.visits:
        if v.leg:
            legs.append((v.from_node, v.resource.id, v.leg.route_name or v.leg.mode))
    rejected = list(fr.rejected)
    for rid, reason in result.rejections.items():
        r = store.get(rid)
        if r and rid not in selected:
            rejected.append(RejectedResource(resource_id=rid, name=r.name, service=r.service, reason=reason))
    graph = build_plan_graph(uc, fr.eligible, rejected, selected, legs, store.resources)

    return Plan(
        plan_id=str(uuid.uuid4()),
        strategy=strategy,
        created_at=datetime.now().isoformat(timespec="seconds"),
        now=now.isoformat(timespec="minutes"),
        constraints=uc,
        steps=steps,
        resource_ids=selected,
        total_cost_usd=result.total_cost,
        total_travel_min=result.total_travel_min,
        score=result.score,
        feasible=result.feasible,
        unmet_needs=result.unmet,
        explanation=explanation,
        rejected=rejected,
        graph=graph,
    )


def diff_plans(old: Plan, new: Plan, trigger: Optional[str] = None) -> PlanDiff:
    o, n = set(old.resource_ids), set(new.resource_ids)
    return PlanDiff(removed_resource_ids=[r for r in old.resource_ids if r not in n],
                    added_resource_ids=[r for r in new.resource_ids if r not in o], trigger=trigger,
                    travel_delta_min=new.total_travel_min - old.total_travel_min,
                    cost_delta_usd=round(new.total_cost_usd - old.total_cost_usd, 2), feasible=new.feasible)


def _tradeoff(plan: Plan, reference: Optional[Plan]) -> str:
    no_id = all(not store.resources[rid].eligibility.requires_id for rid in plan.resource_ids)
    condition = "no photo ID needed" if no_id else "photo ID needed at some stops"
    if plan.strategy == "recommended" or reference is None:
        return f"Balances travel, cost and intake time; {condition}."
    if plan.strategy == "fastest":
        return f"{reference.total_travel_min - plan.total_travel_min} fewer travel minutes; {condition}."
    saved = reference.total_cost_usd - plan.total_cost_usd
    extra = plan.total_travel_min - reference.total_travel_min
    return f"Saves ${saved:g}; {abs(extra)} {'more' if extra >= 0 else 'fewer'} travel minutes."


def make_bundle(uc: UserConstraints, now: Optional[datetime] = None,
                previous_plan_id: Optional[str] = None) -> PlanBundle:
    plans: list[Plan] = []
    signatures: set = set()
    skipped: list[str] = []
    for strategy in STRATEGIES:
        plan = make_plan(uc, now, strategy=strategy)
        signature = tuple((s.type, s.resource_id, s.mode, s.time_iso) for s in plan.steps)
        if signature in signatures:
            skipped.append(STRATEGY_LABEL.get(strategy, strategy))
            continue
        signatures.add(signature)
        plan.explanation = template(plan)
        plan.tradeoff = _tradeoff(plan, plans[0] if plans else None)
        store.save_plan(plan)
        plans.append(plan)

    note = f"{', '.join(skipped)} produces the same route, so it is shown once. " if skipped else ""
    if len(plans) == 1:
        note += ("Other resources fail the selected requirements, hours, route or budget checks, "
                 "or rank below this route. See checked options.")

    old = store.get_plan(previous_plan_id) if previous_plan_id else None
    diff = None
    if old:
        replacement = next((p for p in plans if p.strategy == old.strategy), plans[0])
        changed = [store.get(rid) for rid in old.resource_ids
                   if store.get(rid) and store.get(rid).status.value != "available"]
        trigger = "; ".join(f"{r.name} is now {r.status.value}" for r in changed) or "Availability was updated"
        diff = diff_plans(old, replacement, trigger)
    return PlanBundle(plans=plans, alternatives_note=note, diff=diff)
