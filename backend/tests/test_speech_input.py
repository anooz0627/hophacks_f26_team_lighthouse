import httpx
import pytest
from fastapi.testclient import TestClient

from app import voice
from app.main import app
from app.routers import speech

client = TestClient(app)


@pytest.fixture(autouse=True)
def configured_voice(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("AIDGRAPH_DISABLE_VOICE", raising=False)


def send(data=b"recorded-audio", content_type="audio/webm;codecs=opus"):
    return client.post("/speech/transcribe", content=data, headers={"content-type": content_type})


def test_transcription_preserves_text_and_passes_audio_to_provider(monkeypatch):
    calls = []

    async def transcribe(data, content_type, extension):
        calls.append((data, content_type, extension))
        return "I need food and a step-free entrance."

    monkeypatch.setattr(voice, "transcribe", transcribe)
    result = send()
    assert result.status_code == 200
    assert result.json() == {"text": "I need food and a step-free entrance."}
    assert calls == [(b"recorded-audio", "audio/webm", "webm")]


def test_unconfigured_voice_does_not_accept_audio(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert send().status_code == 503


@pytest.mark.parametrize(("data", "content_type", "status"), [
    (b"", "audio/webm", 422),
    (b"audio", "text/html", 415),
    (b"x" * 17, "audio/wav", 413),
])
def test_invalid_recording_never_reaches_provider(monkeypatch, data, content_type, status):
    monkeypatch.setattr(speech, "MAX_AUDIO_BYTES", 16)

    async def forbidden(*args):
        pytest.fail("Invalid audio reached the provider")

    monkeypatch.setattr(voice, "transcribe", forbidden)
    assert send(data, content_type).status_code == status


@pytest.mark.parametrize("text", ["", "x" * 10001])
def test_empty_or_oversized_transcript_is_recoverable(monkeypatch, text):
    async def transcribe(*args):
        return text

    monkeypatch.setattr(voice, "transcribe", transcribe)
    assert send().status_code == 422


def test_provider_error_is_not_exposed(monkeypatch):
    async def fail(*args):
        raise RuntimeError("provider details test-key")

    monkeypatch.setattr(voice, "transcribe", fail)
    response = send()
    assert response.status_code == 502
    assert "test-key" not in response.text
    assert "typed text is unchanged" in response.text


@pytest.mark.asyncio
async def test_elevenlabs_request_uses_scribe_and_server_side_auth(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"text": "  A meal nearby.  "})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    assert await voice.transcribe(b"recorded-audio", "audio/mp4", "m4a") == "A meal nearby."
    assert len(calls) == 1
    request = calls[0]
    assert str(request.url) == "https://api.elevenlabs.io/v1/speech-to-text"
    assert request.headers["xi-api-key"] == "test-key"
    assert b"scribe_v2" in request.content
    assert b'recording.m4a' in request.content
    assert b"recorded-audio" in request.content
