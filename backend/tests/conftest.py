import pytest

from app.store import store


@pytest.fixture(autouse=True)
def reset_store():
    store.load()
    store.plans.clear()
    yield
    store.load()
    store.plans.clear()
