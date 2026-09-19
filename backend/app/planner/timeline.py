from __future__ import annotations

from datetime import datetime, timedelta

from ..models import PlanStep, ServiceType
from .search import CALL_MIN, SearchResult
from .timeutil import fmt, intake_deadline_for, window_containing

ACTION = {
    ServiceType.food: "Eat at",
    ServiceType.emergency_housing: "Check in at",
    ServiceType.long_term_assistance: "Visit",
}

MODE_TITLE = {
    "walk": "Walk",
    "car": "Drive",
    "rideshare": "Take a rideshare",
}


def _step(order: int, t: datetime, **kw) -> PlanStep:
    return PlanStep(order=order, time=fmt(t), time_iso=t.isoformat(timespec="minutes"), **kw)


def build_timeline(result: SearchResult, now: datetime) -> list[PlanStep]:
    steps: list[PlanStep] = []
    n = 1
    t = now

    if result.call_first:
        r = result.call_first
        cap = f"{r.capacity} spots reported. " if r.capacity is not None else ""
        steps.append(_step(n, t, type="call", title=f"Call {r.name}", resource_id=r.id,
                           detail=f"{cap}Confirm a place, intake time and required documents. Demo phone: {r.phone}",
                           duration_min=CALL_MIN, lat=r.lat, lng=r.lng))
        n += 1

    for v in result.visits:
        r = v.resource
        leg = v.leg
        if leg is not None:
            depart = v.arrival - timedelta(minutes=leg.duration_min)
            mode_title = MODE_TITLE.get(leg.mode, f"Take {leg.route_name}")
            steps.append(_step(n, depart, type="travel", title=f"{mode_title} to {r.name}", detail=leg.describe(),
                               route_id=leg.route_id, mode=leg.mode, duration_min=leg.duration_min,
                               cost_usd=leg.cost_usd, polyline=leg.polyline, day_label=v.day_label,
                               resource_id=r.id))
            n += 1
        win = window_containing(r, v.arrival)
        detail_bits = []
        if win:
            deadline = intake_deadline_for(r, win[0])
            if deadline:
                detail_bits.append(f"Intake until {fmt(deadline)}")
            else:
                detail_bits.append(f"Open until {fmt(win[1])}")
        if r.notes:
            detail_bits.append(r.notes)
        bring = list(r.eligibility.required_documents)
        steps.append(_step(n, v.arrival, type="visit", title=f"{ACTION[r.service]} {r.name}", resource_id=r.id,
                           detail=" · ".join(detail_bits), lat=r.lat, lng=r.lng, warnings=v.warnings, bring=bring,
                           day_label=v.day_label, cost_usd=r.cost))
        n += 1

    if result.unmet:
        names = ", ".join(u.value.replace("_", " ") for u in result.unmet)
        steps.append(_step(n, result.visits[-1].departure if result.visits else t, type="note",
                           title="Could not schedule",
                           detail=f"No feasible option found for: {names}. Call 211 for additional options."))
    steps.sort(key=lambda step: step.time_iso)
    for index, step in enumerate(steps, 1):
        step.order = index
    return steps
