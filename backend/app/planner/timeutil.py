from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from ..models import Resource

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def window_containing(resource: Resource, t: datetime) -> Optional[tuple[datetime, datetime]]:
    for w in resource.hours:
        for day_offset in (0, 1):
            day = (t - timedelta(days=day_offset)).date()
            if DAYS[day.weekday()] not in w.days:
                continue
            open_dt = datetime.combine(day, parse_hhmm(w.open))
            close_dt = datetime.combine(day, parse_hhmm(w.close))
            if close_dt <= open_dt:
                close_dt += timedelta(days=1)
            if open_dt <= t < close_dt:
                return open_dt, close_dt
    return None


def intake_deadline_for(resource: Resource, open_dt: datetime) -> Optional[datetime]:
    if not resource.intake_deadline:
        return None
    d = datetime.combine(open_dt.date(), parse_hhmm(resource.intake_deadline))
    if d < open_dt:
        d += timedelta(days=1)
    return d


def next_opening(resource: Resource, after: datetime, within_days: int = 3) -> Optional[tuple[datetime, datetime]]:
    best: Optional[tuple[datetime, datetime]] = None
    for d in range(within_days + 1):
        day = (after + timedelta(days=d)).date()
        for w in resource.hours:
            if DAYS[day.weekday()] not in w.days:
                continue
            open_dt = datetime.combine(day, parse_hhmm(w.open))
            close_dt = datetime.combine(day, parse_hhmm(w.close))
            if close_dt <= open_dt:
                close_dt += timedelta(days=1)
            if open_dt >= after and (best is None or open_dt < best[0]):
                best = (open_dt, close_dt)
    return best


def describe_hours(resource: Resource) -> str:
    parts = []
    for w in resource.hours:
        days = "daily" if len(w.days) == 7 else "/".join(d.capitalize() for d in w.days)
        parts.append(f"{days} {w.open}-{w.close}")
    return "; ".join(parts)
