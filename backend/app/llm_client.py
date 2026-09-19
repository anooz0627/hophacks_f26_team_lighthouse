from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_MODEL = "gemini-2.5-flash"


def model_id() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


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
        return genai.Client(api_key=key)
    except Exception:
        return None


def generation_config(**overrides) -> dict:
    config = {
        "temperature": 0.0,
        "thinking_config": {"thinking_budget": 0},
    }
    config.update(overrides)
    return config
