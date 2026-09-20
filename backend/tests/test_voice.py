import os

os.environ["LIGHTHOUSE_DISABLE_LLM"] = "1"

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import voice
from app.extraction.fallback import extract
from app.main import app
from app.planner.service import make_plan
from app.voice import speech_script, spoken_time

client = TestClient(app)
NOW = datetime(2026, 9, 17, 18)
SCENARIO = "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight."


@pytest.mark.parametrize(("hhmm", "spoken"), [("18:00", "6 PM"), ("07:05", "7:05 AM"), ("00:10", "12:10 AM"), ("12:00", "12 PM")])
def test_times_are_spoken_naturally(hhmm, spoken):
    assert spoken_time(hhmm) == spoken


def test_script_covers_every_step_in_order():
    plan = make_plan(extract(SCENARIO), NOW)
    script = speech_script(plan)
    positions = [script.index(step.title[1:]) for step in plan.steps if step.type != "note"]
    assert positions == sorted(positions)
    assert "Tonight." in script and "Tomorrow." in script
    assert "Call ahead" in script


def test_script_names_unmet_needs():
    uc = extract(SCENARIO)
    uc.constraints.budget_usd = 0
    uc.constraints.transport = "walking"
    uc.constraints.accessibility = ["limited_walking"]
    plan = make_plan(uc, NOW)
    if plan.unmet_needs:
        assert "could not schedule" in speech_script(plan)


def test_audio_requires_a_saved_plan_and_a_configured_voice(monkeypatch):
    assert client.get("/plans/nope/audio").status_code == 404
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    assert client.get(f"/plans/{plan['plan_id']}/script").json()["text"].startswith("Here is your plan.")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert client.get(f"/plans/{plan['plan_id']}/audio").status_code == 503
    assert client.get("/health").json()["voice"] is False


def test_audio_streams_mpeg_and_caches(monkeypatch):
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    calls = []
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    monkeypatch.setattr(voice, "synthesize", lambda text: calls.append(text) or b"ID3fake")
    voice._cache.clear()
    first = client.get(f"/plans/{plan['plan_id']}/audio")
    second = client.get(f"/plans/{plan['plan_id']}/audio")
    assert first.status_code == 200 and first.headers["content-type"] == "audio/mpeg"
    assert first.content == b"ID3fake" == second.content
    assert len(calls) == 1
    assert client.get("/health").json()["voice"] is True


def test_audio_failure_is_a_502(monkeypatch):
    plan = client.post("/plan", json={"text": SCENARIO, "now": NOW.isoformat()}).json()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")

    def boom(text):
        raise RuntimeError("upstream")

    monkeypatch.setattr(voice, "synthesize", boom)
    voice._cache.clear()
    assert client.get(f"/plans/{plan['plan_id']}/audio").status_code == 502


def test_say_endpoint_reads_arbitrary_text(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert client.post("/speech/say", json={"text": "I need shelter tonight."}).status_code == 503
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    monkeypatch.setattr(voice, "synthesize", lambda text: b"ID3card")
    voice._cache.clear()
    r = client.post("/speech/say", json={"text": "I need shelter tonight."})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3card"
    assert client.post("/speech/say", json={"text": ""}).status_code == 422
