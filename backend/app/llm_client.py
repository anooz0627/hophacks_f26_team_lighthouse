from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_FALLBACKS = "gemini-3.6-flash,gemini-3.7-flash"
RETRYABLE = ("RESOURCE_EXHAUSTED", "429", "NOT_FOUND", "404", "UNAVAILABLE", "503")


def model_id() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def model_chain() -> list[str]:
    extra = os.environ.get("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACKS)
    chain = [model_id()] + [m.strip() for m in extra.split(",") if m.strip()]
    return list(dict.fromkeys(chain))


def llm_enabled() -> bool:
    if os.environ.get("AIDGRAPH_DISABLE_LLM"):
        return False
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


@lru_cache(maxsize=1)
def get_client():
    if not llm_enabled():
        return None
    try:
        from google import genai

        key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
        return genai.Client(api_key=key, http_options={"timeout": 12000})
    except Exception:
        return None


def generation_config(**overrides) -> dict:
    config = {
        "temperature": 0.0,
        "thinking_config": {"thinking_budget": 0},
    }
    config.update(overrides)
    return config


def generate(contents, config: dict):
    client = get_client()
    if client is None:
        return None
    last: Exception | None = None
    for model in model_chain():
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            last = exc
            if not any(token in str(exc) for token in RETRYABLE):
                raise
    if last is not None:
        raise last
    return None
