from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from ..explain import template
from ..models import (BlockedNeed, LatLng, Plan, PlanBundle, PlanDiff, Progress, RejectedResource, ServiceType, Strategy,
                      UnroutedResource, UserConstraints)
from ..store import store
from .filters import apply_filters
from .graph import build_plan_graph, build_travel_graph
from .search import local_time, search
from .timeline import build_timeline
from .travel import haversine_km

STRATEGIES: tuple[Strategy, ...] = ("recommended", "fastest", "lowest_cost")
NEED_WORD = {ServiceType.emergency_housing: "shelter", ServiceType.food: "food", ServiceType.long_term_assistance: "longer-term help"}
CAUSE_ORDER = ("status", "id", "budget", "route", "hours", "eligibility")
BLOCKED_TEXT = {
    "id": ("Every {word} option we checked requires a photo ID.", "Look for a place that does not require ID, or get help replacing your ID first."),
    "budget": ("Travel or fees for every {word} option exceed your budget.", "A free route or fare help is needed. Tell us if your budget changed."),
    "route": ("No {word} option is within your walking limit from where you are.", "Tell us if you can walk farther, or use a bus or rideshare."),
    "hours": ("Every {word} option is closed by the time you could arrive.", "We scheduled the next opening where possible. Call 211 for after-hours options."),
    "status": ("Every {word} option is currently full, closed or unavailable.", "Check again later or call 211."),
    "eligibility": ("The {word} options we checked have requirements you do not meet (age, household or accessibility).", "Confirm requirements by phone; some rules have exceptions."),
    "none": ("No listed resource offers {word}.", "Call 211 for options outside this dataset."),
}


def classify_reason(reason: str) -> str:
    r = reason.lower()
    if "photo id" in r:
        return "id"
    if "budget" in r:
        return "budget"
    if "no route" in r or "walking limit" in r:
        return "route"
    if "currently" in r or "service delayed" in r:
        return "status"
    if "close" in r or "opening" in r:
        return "hours"
    return "eligibility"


def diagnose_blocked(unmet: list[ServiceType], rejected: list[RejectedResource], search_rejections: dict[str, str]) -> list[BlockedNeed]:
    blocked: list[BlockedNeed] = []
    for need in unmet:
        reasons: dict[str, str] = {}
        for rj in rejected:
            if rj.service == need:
                reasons[rj.resource_id] = rj.reason
        for rid, reason in search_rejections.items():
            r = store.get(rid)
            if r and r.service == need and rid not in reasons:
                reasons[rid] = reason
        counts: dict[str, int] = {}
        for reason in reasons.values():
            c = classify_reason(reason)
            counts[c] = counts.get(c, 0) + 1
        cause = max(counts, key=lambda c: (counts[c], -CAUSE_ORDER.index(c) if c in CAUSE_ORDER else 0)) if counts else "none"
        summary, suggestion = BLOCKED_TEXT[cause]
        word = NEED_WORD[need]
        first_step = None
        if cause == "id":
            helper = next((r for r in store.all_resources() if "id_replacement" in r.tags and r.status.value == "available"), None)
            if helper:
                first_step = helper.id
                suggestion = f"First, get help replacing your ID at {helper.name}; then shelters that require ID open up."
        blocked.append(BlockedNeed(need=need, cause=cause, summary=summary.format(word=word), suggestion=suggestion,
                                   first_step_resource_id=first_step, checked=len(reasons)))
    return blocked
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
    unrouted = [UnroutedResource(
        resource_id=r.id,
        distance_km=round(haversine_km((origin.lat, origin.lng), (r.lat, r.lng)), 1),
        reason="Travel time and cost are not confirmed for your starting point and travel preferences.",
        warnings=fr.warnings.get(r.id, []),
    ) for r in fr.eligible if r.service in result.unmet
        and result.rejections.get(r.id) == "no route fits your transportation or walking limits"]
    unrouted.sort(key=lambda item: (item.distance_km, item.resource_id))
    blocked = diagnose_blocked(result.unmet, rejected, result.rejections)

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
        unrouted_resources=unrouted,
        blocked=blocked,
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


def apply_progress(old: Plan, uc: UserConstraints, progress: Progress) -> tuple[UserConstraints, Optional[LatLng]]:
    uc = uc.model_copy(deep=True)
    done = [s for s in old.steps if s.order in set(progress.completed_orders)]
    satisfied: set[ServiceType] = set()
    origin: Optional[LatLng] = progress.current_location
    for step in done:
        resource = store.get(step.resource_id) if step.resource_id else None
        if resource is None:
            continue
        if step.type == "visit":
            satisfied.add(resource.service)
            if any(n.type == "note" and n.resource_id == resource.id and "Dinner" in n.title for n in old.steps):
                satisfied.add(ServiceType.food)
        if origin is None and step.type in ("visit", "travel"):
            origin = LatLng(lat=resource.lat, lng=resource.lng)
    remaining = [n for n in uc.needs if n.type not in satisfied]
    if remaining:
        uc.needs = remaining
    if origin is not None:
        uc.constraints.current_location = origin
    return uc, origin


def progress_floor(old: Plan, progress: Progress) -> Optional[datetime]:
    done = [s for s in old.steps if s.order in set(progress.completed_orders) and s.type != "note"]
    if not done:
        return None
    last = max(done, key=lambda s: s.order)
    floor = datetime.fromisoformat(last.time_iso)
    resource = store.get(last.resource_id) if last.resource_id else None
    if last.type == "visit" and resource is not None:
        from .search import DWELL_MIN
        floor += timedelta(minutes=DWELL_MIN[resource.service])
    return floor


def make_bundle(uc: UserConstraints, now: Optional[datetime] = None,
                previous_plan_id: Optional[str] = None, progress: Optional[Progress] = None) -> PlanBundle:
    old = store.get_plan(previous_plan_id) if previous_plan_id else None
    origin: Optional[LatLng] = None
    if old is not None and progress is not None:
        uc, origin = apply_progress(old, uc, progress)
        now = progress.now or now
        floor = progress_floor(old, progress)
        if floor is not None:
            now = max(local_time(now) if now else floor, floor)
    now = now or datetime.now(ZoneInfo("America/New_York"))
    plans: list[Plan] = []
    signatures: set = set()
    skipped: list[str] = []
    for strategy in STRATEGIES:
        plan = make_plan(uc, now, origin=origin, strategy=strategy)
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

    diff = None
    if old:
        replacement = next((p for p in plans if p.strategy == old.strategy), plans[0])
        changed = [store.get(rid) for rid in old.resource_ids
                   if store.get(rid) and store.get(rid).status.value != "available"]
        trigger = "; ".join(f"{r.name} is now {r.status.value}" for r in changed) or "Availability was updated"
        diff = diff_plans(old, replacement, trigger)
        if progress is not None:
            finished = {s.resource_id for s in old.steps
                        if s.type == "visit" and s.order in set(progress.completed_orders)}
            diff.removed_resource_ids = [rid for rid in diff.removed_resource_ids if rid not in finished]
    return PlanBundle(plans=plans, alternatives_note=note, diff=diff)
