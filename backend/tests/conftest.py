import os

os.environ.setdefault("LIGHTHOUSE_DATASET", "demo")
os.environ.setdefault("LIGHTHOUSE_DISABLE_LLM", "1")

import pytest

from app.store import store


@pytest.fixture(autouse=True)
def reset_store():
    store.load("demo")
    store.plans.clear()
    yield
    store.load("demo")
    store.plans.clear()
