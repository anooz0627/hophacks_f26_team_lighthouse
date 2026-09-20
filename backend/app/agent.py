from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .extraction.fallback import NEIGHBORHOODS
from .llm_client import generate, generation_config, get_client
from .models import DisruptionResponse, LatLng, Plan, PlanDiff, Progress, ResourceStatus, ServiceType
from .planner.search import local_time
from .planner.service import make_bundle
from .store import store

STATUS_WORDS = {
    "full": ResourceStatus.full, "no beds": ResourceStatus.full, "no room": ResourceStatus.full,
    "no space": ResourceStatus.full, "turned me away": ResourceStatus.full,
    "closed": ResourceStatus.closed, "unavailable": ResourceStatus.unavailable, "delayed": ResourceStatus.delayed,
}
DEFAULT_LATE_MIN = 20
DEFAULT_BUS_DELAY_MIN = 15
DEFAULT_MISSED_BUS_MIN = 15

LATE = re.compile(r"\b(?:running|be|am|i'?m)\s+(?:about\s+)?(\d{1,3})\s*(?:min|mins|minutes)\s+late\b|"
                  r"\b(\d{1,3})\s*(?:min|mins|minutes)\s+(?:late|behind)\b|\blate by\s+(\d{1,3})\b", re.I)
RUNNING_LATE = re.compile(r"\b(running late|behind schedule|got held up|took longer)\b", re.I)
MISSED_BUS = re.compile(r"\b(missed|miss)\s+(?:the|my|our)?\s*bus\b", re.I)
BUS_DELAY = re.compile(r"\bbus(?:es)?\s+(?:is|are)?\s*(?:running\s+)?(?:late|delayed)(?:\s+(?:by\s+)?(\d{1,3})\s*(?:min|mins|minutes))?", re.I)
LOST_ID = re.compile(r"\b(lost my (?:id|wallet|license)|don'?t have (?:my |an )?id|no id)\b", re.I)
BUDGET = re.compile(r"\b(?:only have|left with|down to|have)\s+\$\s?(\d+(?:\.\d+)?)\b|\bspent\s+\$\s?(\d+(?:\.\d+)?)\b", re.I)
CANT_WALK = re.compile(r"\b(can'?t walk (?:far|much|anymore)|hurt my (?:leg|foot|ankle|knee)|too tired to walk)\b", re.I)
TOO_FAR = re.compile(r"\b(too far|that'?s far|can'?t walk that|not walking that|no way i can walk|shorter walk)\b", re.I)
CAN_WALK = re.compile(r"\b(i can walk|walking is fine|that'?s fine|ok to walk|i'?ll walk)\b", re.I)
AT_PLACE = re.compile(r"\b(?:i'?m|i am|we'?re|we are)\s+(?:now\s+)?(?:at|in|near)\s+(?:the\s+)?([A-Za-z][A-Za-z' .&]+?)(?=[.,!?;]|\s+(?:and|but|now)\b|$)", re.I)
DONE_EATING = re.compile(r"\b(finished|done|already)\s+(?:with\s+)?(?:eating|dinner|lunch|breakfast|my meal)|\b(?:i|we)\s+(?:already\s+)?ate\b", re.I)
CHECKED_IN = re.compile(r"\b(checked in|got a bed|they let me in|i'?m inside)\b", re.I)

SYSTEM = (
    "You translate a short message from someone following a step-by-step assistance plan into tool calls. "
    "The message describes something that changed: they are late, missed a bus, a place turned them away, "
    "a bus is delayed, they lost a document, they moved somewhere, they finished a step, or their money changed. "
    "Call every tool that applies, with values taken only from the message. Do not guess values that are not stated; "
    "use the tool defaults. Never invent places, times or statuses. If nothing in the message changes the plan, call no tools."
)

TOOLS: list[dict[str, Any]] = [
    {"name": "shift_time", "description": "The person is behind schedule. Move the current time forward.",
     "parameters": {"type": "object", "properties": {
         "minutes": {"type": "integer", "description": "Minutes late. Use 15 for a missed bus, 20 if unstated."}},
         "required": ["minutes"]}},
    {"name": "mark_resource_status", "description": "A place in or near the plan is full, closed, unavailable or delayed.",
     "parameters": {"type": "object", "properties": {
         "resource_id": {"type": "string", "description": "Id of the resource from the plan context."},
         "status": {"type": "string", "enum": ["full", "closed", "unavailable", "delayed"]}},
         "required": ["resource_id", "status"]}},
    {"name": "report_transit_delay", "description": "A bus route is running late.",
     "parameters": {"type": "object", "properties": {
         "route_id": {"type": "string", "description": "Route id from the context, or empty for the route in the plan."},
         "minutes": {"type": "integer", "description": "Delay in minutes. Use 15 if unstated."}},
         "required": ["minutes"]}},
    {"name": "set_location", "description": "The person says where they are now.",
     "parameters": {"type": "object", "properties": {
         "place": {"type": "string", "description": "Neighborhood or resource name exactly as it appears in the context."}},
         "required": ["place"]}},
    {"name": "mark_step_done", "description": "The person completed a step of the plan.",
     "parameters": {"type": "object", "properties": {
         "order": {"type": "integer", "description": "Step order number from the context."}},
         "required": ["order"]}},
    {"name": "update_constraint", "description": "A personal detail changed: they lost their ID, have less money, or cannot walk far.",
     "parameters": {"type": "object", "properties": {
         "field": {"type": "string", "enum": ["has_id", "budget_usd", "limited_walking", "max_walk_km"]},
         "value": {"type": "string", "description": "false for has_id, a number for budget_usd, true for limited_walking, a distance in km for max_walk_km (use 3 when a walk is too far, 8 when they say a long walk is fine)."}},
         "required": ["field", "value"]}},
]


@dataclass
class Call:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


GENERIC_WORDS = {
    "center", "centre", "house", "mission", "resource", "housing", "downtown", "shelter", "street", "kitchen",
    "community", "emergency", "night", "overnight", "tonight", "baltimore", "program", "programs", "service",
    "services", "food", "pantry", "dinner", "meals", "meal", "family", "families", "drop", "division", "women",
    "men", "youth", "hope", "place", "health", "care", "homeless", "city", "east", "west", "north", "south",
    "eastside", "westside", "early", "late", "daily", "bread",
}


def _match_resource(text: str, plan: Plan) -> Optional[str]:
    lowered = text.lower()
    candidates = [store.get(rid) for rid in plan.resource_ids] + store.all_resources()
    for r in candidates:
        if r is None:
            continue
        name = r.name.lower()
        if name in lowered:
            return r.id
    for rid in plan.resource_ids:
        r = store.get(rid)
        if r is None:
            continue
        words = [w for w in re.split(r"[^a-z0-9']+", r.name.lower()) if len(w) > 3 and w not in GENERIC_WORDS]
        if any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in words):
            return r.id
    return None


def _plan_route_id(plan: Plan) -> Optional[str]:
    for step in plan.steps:
        if step.type == "travel" and step.route_id:
            return step.route_id.split("+")[0]
    return store.transit.routes[0].id if store.transit.routes else None


def _match_route(text: str, plan: Plan) -> Optional[str]:
    lowered = text.lower()
    for route in store.transit.routes:
        key = route.name.lower().replace("(approx.)", "").strip()
        if key in lowered or key.split()[-1] in lowered.split():
            return route.id
    return _plan_route_id(plan)


def parse_rules(text: str, plan: Plan) -> list[Call]:
    calls: list[Call] = []
    m = LATE.search(text)
    if m:
        calls.append(Call("shift_time", {"minutes": int(next(g for g in m.groups() if g))}))
    elif MISSED_BUS.search(text):
        calls.append(Call("shift_time", {"minutes": DEFAULT_MISSED_BUS_MIN}))
    elif RUNNING_LATE.search(text):
        calls.append(Call("shift_time", {"minutes": DEFAULT_LATE_MIN}))

    m = BUS_DELAY.search(text)
    if m:
        calls.append(Call("report_transit_delay", {"route_id": _match_route(text, plan) or "",
                                                   "minutes": int(m.group(1)) if m.group(1) else DEFAULT_BUS_DELAY_MIN}))

    for phrase, status in STATUS_WORDS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.I):
            rid = _match_resource(text, plan)
            if rid is None:
                rid = next((r for r in plan.resource_ids if store.get(r) and store.get(r).service == ServiceType.emergency_housing), None)
            if rid and not (status == ResourceStatus.delayed and m):
                calls.append(Call("mark_resource_status", {"resource_id": rid, "status": status.value}))
            break

    if LOST_ID.search(text):
        calls.append(Call("update_constraint", {"field": "has_id", "value": "false"}))
    m = BUDGET.search(text)
    if m:
        if m.group(1):
            calls.append(Call("update_constraint", {"field": "budget_usd", "value": m.group(1)}))
        elif plan.constraints.constraints.budget_usd is not None:
            left = max(0.0, plan.constraints.constraints.budget_usd - float(m.group(2)))
            calls.append(Call("update_constraint", {"field": "budget_usd", "value": str(left)}))
    if CANT_WALK.search(text):
        calls.append(Call("update_constraint", {"field": "limited_walking", "value": "true"}))
    elif TOO_FAR.search(text):
        calls.append(Call("update_constraint", {"field": "max_walk_km", "value": "3"}))
    elif CAN_WALK.search(text):
        calls.append(Call("update_constraint", {"field": "max_walk_km", "value": "8"}))

    m = AT_PLACE.search(text)
    if m:
        calls.append(Call("set_location", {"place": m.group(1).strip()}))

    if DONE_EATING.search(text):
        for step in plan.steps:
            r = store.get(step.resource_id) if step.resource_id else None
            if step.type == "visit" and r and r.service == ServiceType.food:
                calls.append(Call("mark_step_done", {"order": step.order}))
                break
    if CHECKED_IN.search(text):
        for step in plan.steps:
            r = store.get(step.resource_id) if step.resource_id else None
            if step.type == "visit" and r and r.service == ServiceType.emergency_housing:
                calls.append(Call("mark_step_done", {"order": step.order}))
                break
    return calls


def _context(plan: Plan, progress: Progress) -> str:
    resources = [{"id": rid, "name": store.get(rid).name, "service": store.get(rid).service.value}
                 for rid in plan.resource_ids if store.get(rid)]
    others = [{"id": r.id, "name": r.name} for r in store.all_resources() if r.id not in plan.resource_ids]
    return json.dumps({
        "now": plan.now,
        "completed_orders": progress.completed_orders,
        "note": "Steps listed in completed_orders are already finished. Never mark them again and never move the person back before them.",
        "steps": [{"order": s.order, "time": s.time, "type": s.type, "title": s.title, "resource_id": s.resource_id,
                   "route_id": s.route_id} for s in plan.steps],
        "resources_in_plan": resources,
        "other_resources": others,
        "bus_routes": [{"id": r.id, "name": r.name} for r in store.transit.routes],
        "neighborhoods": list(NEIGHBORHOODS),
        "constraints": {"budget_usd": plan.constraints.constraints.budget_usd, "has_id": plan.constraints.constraints.has_id},
    }, ensure_ascii=False)


def parse_llm(text: str, plan: Plan, progress: Progress) -> Optional[list[Call]]:
    if get_client() is None:
        return None
    try:
        from google.genai import types
        tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in TOOLS])]
        resp = generate(
            [{"role": "user", "parts": [{"text": f"Plan context:\n{_context(plan, progress)}\n\nMessage from the person:\n{text}"}]}],
            generation_config(system_instruction=SYSTEM, tools=tools,
                              tool_config={"function_calling_config": {"mode": "AUTO"}},
                              automatic_function_calling={"disable": True}),
        )
        if resp is None:
            return None
        return [Call(fc.name, dict(fc.args or {})) for fc in (resp.function_calls or [])]
    except Exception:
        return None


def _locate(place: str, plan: Plan) -> Optional[tuple[str, LatLng]]:
    lowered = place.lower().strip()
    for name, (lat, lng) in NEIGHBORHOODS.items():
        if name.lower() in lowered or lowered in name.lower():
            return name, LatLng(lat=lat, lng=lng)
    rid = _match_resource(place, plan)
    if rid:
        r = store.get(rid)
        return r.name, LatLng(lat=r.lat, lng=r.lng)
    return None


def apply_calls(calls: list[Call], plan: Plan, progress: Progress) -> tuple[Progress, list[str], list[str]]:
    uc = plan.constraints.model_copy(deep=True)
    now = local_time(progress.now) if progress.now else datetime.fromisoformat(plan.now)
    progress = progress.model_copy(deep=True)
    actions: list[str] = []
    triggers: list[str] = []
    for call in calls:
        a = call.args
        try:
            if call.name == "shift_time":
                minutes = max(0, min(int(a.get("minutes", DEFAULT_LATE_MIN)), 720))
                now = now + timedelta(minutes=minutes)
                actions.append(f"Moved your start to {now.strftime('%-I:%M %p')} ({minutes} min later)")
                triggers.append(f"you are {minutes} minutes behind")
            elif call.name == "mark_resource_status":
                r = store.get(str(a.get("resource_id", "")))
                status = ResourceStatus(str(a.get("status", "full")))
                if r is not None:
                    store.set_status(r.id, status)
                    actions.append(f"Marked {r.name} as {status.value}")
                    triggers.append(f"{r.name} is now {status.value}")
            elif call.name == "report_transit_delay":
                route = store.route(str(a.get("route_id") or "")) or store.route(_plan_route_id(plan) or "")
                minutes = max(0, min(int(a.get("minutes", DEFAULT_BUS_DELAY_MIN)), 180))
                if route is not None:
                    store.set_delay(route.id, minutes)
                    actions.append(f"Added a {minutes} min delay to {route.name}")
                    triggers.append(f"{route.name} is delayed {minutes} min")
            elif call.name == "set_location":
                found = _locate(str(a.get("place", "")), plan)
                if found:
                    label, point = found
                    progress.current_location = point
                    uc.constraints.location_label = label
                    actions.append(f"Starting from {label}")
                    triggers.append(f"you are at {label}")
            elif call.name == "mark_step_done":
                order = int(a.get("order", 0))
                step = next((s for s in plan.steps if s.order == order), None)
                if step and order not in progress.completed_orders:
                    progress.completed_orders.append(order)
                    actions.append(f"Marked step {order} done: {step.title}")
            elif call.name == "update_constraint":
                fld, value = str(a.get("field", "")), str(a.get("value", "")).strip().lower()
                if fld == "has_id":
                    uc.constraints.has_id = value in ("true", "yes", "1")
                    actions.append("Photo ID: " + ("available" if uc.constraints.has_id else "not available"))
                    triggers.append("your photo ID is no longer available" if not uc.constraints.has_id else "you now have photo ID")
                elif fld == "budget_usd":
                    uc.constraints.budget_usd = max(0.0, float(value))
                    actions.append(f"Budget set to ${uc.constraints.budget_usd:g}")
                    triggers.append(f"your budget is now ${uc.constraints.budget_usd:g}")
                elif fld == "max_walk_km":
                    uc.constraints.max_walk_km = max(0.2, min(float(value), 15.0))
                    actions.append(f"Walking limit set to {uc.constraints.max_walk_km:g} km")
                    triggers.append(f"you asked for walks under {uc.constraints.max_walk_km:g} km")
                elif fld == "limited_walking" and value in ("true", "yes", "1"):
                    if "limited_walking" not in uc.constraints.accessibility:
                        uc.constraints.accessibility.append("limited_walking")
                    actions.append("Limited walking: short walks only")
                    triggers.append("you can only walk short distances")
        except (ValueError, KeyError, TypeError):
            continue
    progress.now = now
    plan.constraints = uc
    return progress, actions, triggers


def _progress_note(plan: Plan, progress: Progress) -> str:
    done = [s for s in plan.steps if s.order in set(progress.completed_orders) and s.type != "note"]
    total = [s for s in plan.steps if s.type != "note"]
    if not done:
        return ""
    last = max(done, key=lambda s: s.order)
    where = store.get(last.resource_id).name if last.resource_id and store.get(last.resource_id) else last.title
    return f"You’ve finished {len(done)} of {len(total)} steps, so I’m continuing from {where}."


def _message(actions: list[str], diff: Optional[PlanDiff], plans_feasible: bool, progress_note: str = "") -> str:
    if not actions:
        base = "I didn’t find anything in that message that changes your plan. Your current steps still stand."
        return f"{progress_note} {base}".strip()
    parts = ["Got it: " + "; ".join(actions) + "."]
    if progress_note:
        parts.append(progress_note)
    if diff and (diff.removed_resource_ids or diff.added_resource_ids):
        removed = ", ".join(store.get(r).name for r in diff.removed_resource_ids if store.get(r))
        added = ", ".join(store.get(r).name for r in diff.added_resource_ids if store.get(r))
        if removed and added:
            parts.append(f"{removed} no longer fits, so the plan now goes to {added}.")
        elif added:
            parts.append(f"Added {added} to your plan.")
        elif removed:
            parts.append(f"{removed} was removed from your plan.")
    elif diff:
        parts.append("The same places still work; the times have been updated.")
    if not plans_feasible:
        parts.append("Some needs could not be scheduled. Check the reasons below or call 211.")
    return " ".join(parts)


def handle(plan_id: str, text: str, progress: Optional[Progress]) -> DisruptionResponse:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise KeyError(plan_id)
    plan = plan.model_copy(deep=True)
    progress = progress or Progress()
    calls = parse_llm(text, plan, progress)
    source = "llm"
    if calls is None:
        calls = parse_rules(text, plan)
        source = "rules"
    elif not calls:
        rule_calls = parse_rules(text, plan)
        if rule_calls:
            calls, source = rule_calls, "rules"
    progress, actions, triggers = apply_calls(calls, plan, progress)
    bundle = make_bundle(plan.constraints, progress.now, previous_plan_id=plan_id, progress=progress)
    if bundle.diff is not None and triggers:
        bundle.diff.trigger = "; ".join(triggers)
    feasible = all(p.feasible for p in bundle.plans)
    message = _message(actions, bundle.diff, feasible, _progress_note(plan, progress))
    for item in bundle.plans[0].blocked[:1]:
        message += f" {item.summary} {item.suggestion}"
    return DisruptionResponse(plans=bundle.plans, alternatives_note=bundle.alternatives_note, diff=bundle.diff,
                              previous_plan_id=plan_id, actions=actions, source=source,
                              message=message)
