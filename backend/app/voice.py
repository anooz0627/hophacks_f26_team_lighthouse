from __future__ import annotations

import os
from collections import OrderedDict

import httpx

from .models import Plan
from .store import store

DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"
MODEL = "eleven_multilingual_v2"
MAX_CHARS = 2500

DAY_WORD = {"tonight": "Tonight", "tomorrow": "Tomorrow", "later": "Later this week"}
_cache: OrderedDict[str, bytes] = OrderedDict()


def voice_enabled() -> bool:
    if os.environ.get("AIDGRAPH_DISABLE_VOICE"):
        return False
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE


def spoken_time(hhmm: str) -> str:
    hour, minute = (int(x) for x in hhmm.split(":"))
    suffix = "AM" if hour < 12 else "PM"
    hour = hour % 12 or 12
    return f"{hour}:{minute:02d} {suffix}" if minute else f"{hour} {suffix}"


def speech_script(plan: Plan) -> str:
    lines = ["Here is your plan." if plan.feasible else "Here is a partial plan."]
    contacts_only = bool(plan.unrouted_resources) and not plan.resource_ids
    if contacts_only:
        lines = ["Here are places you can contact. A route is not confirmed."]
    day = None
    for step in ([] if contacts_only else plan.steps):
        if step.type == "note" and "Could not schedule" not in step.title:
            lines.append(step.detail or step.title)
            continue
        if step.day_label != day:
            day = step.day_label
            lines.append(f"{DAY_WORD.get(day, day)}.")
        sentence = f"At {spoken_time(step.time)}, {step.title[0].lower()}{step.title[1:]}."
        if step.type == "visit" and step.bring:
            sentence += f" Bring {', '.join(step.bring)}."
        if step.type == "travel" and step.duration_min:
            sentence += f" About {step.duration_min} minutes."
        lines.append(sentence)
    if plan.unrouted_resources:
        lines.append("Check travel time, fare, opening hours and availability before leaving.")
        for option in plan.unrouted_resources:
            resource = store.get(option.resource_id)
            if resource:
                lines.append(f"{resource.name}, at {resource.address}. {' '.join(option.warnings)}")
    if plan.unmet_needs:
        names = ", ".join(n.value.replace("_", " ") for n in plan.unmet_needs)
        lines.append(f"We could not schedule {names}. Call 2 1 1 for more options.")
    else:
        lines.append("All times are estimates. Call ahead before you travel.")
    return " ".join(lines)[:MAX_CHARS]


def synthesize(text: str) -> bytes:
    response = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id()}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.content


def audio_for(plan_id: str, text: str) -> bytes:
    key = f"{plan_id}:{hash(text)}"
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    data = synthesize(text)
    _cache[key] = data
    if len(_cache) > 32:
        _cache.popitem(last=False)
    return data


async def transcribe(data: bytes, content_type: str, extension: str) -> str:
    async with httpx.AsyncClient(timeout=35.0) as client:
        response = await client.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            data={"model_id": "scribe_v2", "tag_audio_events": "false", "diarize": "false"},
            files={"file": (f"recording.{extension}", data, content_type)},
        )
    response.raise_for_status()
    text = response.json().get("text", "")
    if not isinstance(text, str):
        raise ValueError("Invalid transcript")
    return text.strip()
