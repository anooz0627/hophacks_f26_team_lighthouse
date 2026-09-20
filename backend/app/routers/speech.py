from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import voice

router = APIRouter(tags=["speech"])
MAX_AUDIO_BYTES = 10 * 1024 * 1024
AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
}


@router.post("/speech/transcribe")
async def transcribe(request: Request) -> dict[str, str]:
    if not voice.voice_enabled():
        raise HTTPException(503, "Voice input is unavailable. You can still type your situation.")
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in AUDIO_TYPES:
        raise HTTPException(415, "This audio format is not supported. Please try another browser.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "The recording is too large. Try a shorter recording.")
        data.extend(chunk)
    if not data:
        raise HTTPException(422, "The recording was empty. Please try again.")
    try:
        text = await voice.transcribe(bytes(data), content_type, AUDIO_TYPES[content_type])
    except Exception as exc:
        raise HTTPException(502, "Voice input is temporarily unavailable. Your typed text is unchanged.") from exc
    if not text:
        raise HTTPException(422, "No speech was recognized. Please try again or type your situation.")
    if len(text) > 10000:
        raise HTTPException(422, "The transcript is too long. Try a shorter recording.")
    return {"text": text}


class SayRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


@router.post("/speech/say")
def say(body: SayRequest) -> Response:
    if not voice.voice_enabled():
        raise HTTPException(503, "Voice playback is not configured on this server.")
    try:
        data = voice.audio_for("say", body.text.strip())
    except Exception as exc:
        raise HTTPException(502, "Voice playback is temporarily unavailable.") from exc
    return Response(content=data, media_type="audio/mpeg", headers={"cache-control": "private, max-age=600"})
