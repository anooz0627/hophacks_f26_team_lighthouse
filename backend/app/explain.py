from __future__ import annotations

import json
from collections import OrderedDict

from .llm_client import generate, generation_config, get_client
from .models import Plan
from .voice import speech_script

SYSTEM = (
    "You write a short, calm, practical summary of a plan for someone in crisis. "
    "You are given the plan as JSON. Write 2-3 plain sentences: what to do first, where they will sleep, "
    "and what to bring. Only use facts present in the JSON. Do not add resources, times, or requirements "
    "that are not in the plan. Do not promise that a service will accept them. No markdown, no lists."
)

_cache: OrderedDict[str, str] = OrderedDict()


def template(plan: Plan) -> str:
    visits = [s for s in plan.steps if s.type == "visit"]
    tonight = [s for s in visits if s.day_label == "tonight"]
    if not visits:
        return "No matching route was found in this demo dataset. Try adjusting your details or contact 211 for real local options."
    if not plan.feasible:
        return "This is a partial plan. Some needs could not be scheduled; review the missing needs before traveling."
    parts = []
    first = plan.steps[0]
    parts.append(f"Start at {first.time}: {first.title.lower()}.")
    shelter = next((s for s in tonight if "Check in" in s.title), None)
    if shelter:
        bring = f" Bring: {', '.join(shelter.bring)}." if shelter.bring else ""
        parts.append(f"Estimated arrival at {shelter.title.replace('Check in at ', '')} by {shelter.time}.{bring}")
    tomorrow = [s for s in visits if s.day_label == "tomorrow"]
    if tomorrow:
        parts.append(f"Tomorrow at {tomorrow[0].time}, {tomorrow[0].title.lower()} for longer-term help.")
    return " ".join(parts)


def summarize(plan: Plan) -> str:
    if get_client() is None:
        return template(plan)
    key = f"{plan.plan_id}:{len(plan.steps)}"
    if key in _cache:
        return _cache[key]
    compact = {
        "steps": [{"time": s.time, "day": s.day_label, "title": s.title, "detail": s.detail, "bring": s.bring,
                   "warnings": s.warnings} for s in plan.steps],
        "total_cost_usd": plan.total_cost_usd,
        "unmet_needs": [u.value for u in plan.unmet_needs],
    }
    try:
        resp = generate(json.dumps(compact), generation_config(system_instruction=SYSTEM, max_output_tokens=300))
        text = (resp.text or "").strip() if resp is not None else ""
    except Exception:
        text = ""
    if not text:
        return template(plan)
    _cache[key] = text
    if len(_cache) > 64:
        _cache.popitem(last=False)
    return text


def narrate(plan: Plan) -> str:
    return speech_script(plan)
