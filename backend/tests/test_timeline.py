from datetime import datetime, timedelta

import pytest

from app.models import ServiceType
from app.planner.search import SearchResult, Visit
from app.planner.timeline import build_timeline
from app.planner.travel import TravelLeg
from app.store import store


@pytest.mark.parametrize(("days", "arrival_label"), [(1, "tomorrow"), (2, "later")])
def test_midnight_trip_labels_each_step_by_its_date(days, arrival_label):
    now = datetime(2026, 9, 17, 23, 30)
    arrival = (now + timedelta(days=days)).replace(hour=0, minute=10)
    leg = TravelLeg(mode="walk", duration_min=30, cost_usd=0, polyline=[])
    visit = Visit(
        resource=store.resources["shelter_eastside"],
        arrival=arrival,
        departure=arrival,
        leg=leg,
        from_node="__origin__",
        slack_min=0,
        day_label=arrival_label,
    )
    result = SearchResult(
        visits=[visit], score=0, total_cost=0, total_travel_min=30,
        unmet=[ServiceType.food], rejections={}, feasible=False,
    )

    travel, stay, note = build_timeline(result, now)

    assert travel.type == "travel"
    assert travel.time_iso == (arrival - timedelta(minutes=30)).isoformat(timespec="minutes")
    assert travel.day_label == ("tonight" if days == 1 else "tomorrow")
    assert stay.type == "visit"
    assert stay.day_label == arrival_label
    assert note.type == "note"
    assert note.day_label == arrival_label
