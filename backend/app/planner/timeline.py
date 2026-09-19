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


def _step(now: datetime, time: datetime, **fields) -> PlanStep:
    day_offset = (time.date() - now.date()).days
    day_label = "tonight" if day_offset == 0 else "tomorrow" if day_offset == 1 else "later"
    return PlanStep(
        order=0,
        time=fmt(time),
        time_iso=time.isoformat(timespec="minutes"),
        day_label=day_label,
        **fields,
    )


def build_timeline(result: SearchResult, now: datetime) -> list[PlanStep]:
    steps: list[PlanStep] = []

    if result.call_first:
        resource = result.call_first
        capacity = f"{resource.capacity} spots reported. " if resource.capacity is not None else ""
        phone_label = "Demo phone" if resource.simulated else "Phone"
        steps.append(_step(
            now, now, type="call", title=f"Call {resource.name}", resource_id=resource.id,
            detail=f"{capacity}Confirm a place, intake time and required documents. {phone_label}: {resource.phone}",
            duration_min=CALL_MIN, lat=resource.lat, lng=resource.lng,
        ))

    for visit in result.visits:
        resource = visit.resource
        leg = visit.leg
        if leg is not None:
            departure = visit.arrival - timedelta(minutes=leg.duration_min)
            action = {
                "walk": "Walk",
                "bus": f"Take {leg.route_name}",
                "car": "Drive",
                "rideshare": "Take a rideshare",
            }[leg.mode]
            steps.append(_step(
                now, departure, type="travel", title=f"{action} to {resource.name}",
                detail=leg.describe(), resource_id=resource.id, route_id=leg.route_id,
                mode=leg.mode, duration_min=leg.duration_min, cost_usd=leg.cost_usd,
                polyline=leg.polyline,
            ))

        window = window_containing(resource, visit.arrival)
        details = []
        if window:
            deadline = intake_deadline_for(resource, window[0])
            details.append(f"Intake until {fmt(deadline)}" if deadline else f"Open until {fmt(window[1])}")
        if resource.notes:
            details.append(resource.notes)
        steps.append(_step(
            now, visit.arrival, type="visit", title=f"{ACTION[resource.service]} {resource.name}",
            resource_id=resource.id, detail=" · ".join(details), lat=resource.lat, lng=resource.lng,
            warnings=visit.warnings, bring=list(resource.eligibility.required_documents),
            cost_usd=resource.cost,
        ))

    if result.unmet:
        needs = ", ".join(need.value.replace("_", " ") for need in result.unmet)
        time = result.visits[-1].departure if result.visits else now
        steps.append(_step(
            now, time, type="note", title="Could not schedule",
            detail=f"No feasible option found for: {needs}. Call 211 for additional options.",
        ))

    steps.sort(key=lambda step: step.time_iso)
    for order, step in enumerate(steps, 1):
        step.order = order
    return steps
