from __future__ import annotations

import json

from .llm_client import generation_config, get_client, model_id
from .models import Plan

SYSTEM = (
    "You write a short, calm, practical summary of a plan for someone in crisis. "
    "You are given the plan as JSON. Write 2-3 plain sentences: what to do first, where they will sleep, "
    "and what to bring. Only use facts present in the JSON. Do not add resources, times, or requirements "
    "that are not in the plan. Do not promise that a service will accept them. No markdown, no lists."
)


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
    client = get_client()
    if client is None:
        return template(plan)
    compact = {
        "steps": [{"time": s.time, "day": s.day_label, "title": s.title, "detail": s.detail, "bring": s.bring,
                   "warnings": s.warnings} for s in plan.steps],
        "total_cost_usd": plan.total_cost_usd,
        "unmet_needs": [u.value for u in plan.unmet_needs],
    }
    try:
        resp = client.models.generate_content(
            model=model_id(),
            contents=json.dumps(compact),
            config=generation_config(system_instruction=SYSTEM, max_output_tokens=300),
        )
        text = (resp.text or "").strip()
        return text or template(plan)
    except Exception:
        return template(plan)
