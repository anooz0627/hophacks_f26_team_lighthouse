from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import networkx as nx

from ..models import Need, Resource, ServiceType, Strategy, UserConstraints
from .graph import ORIGIN
from .timeutil import fmt, intake_deadline_for, next_opening, window_containing
from .travel import TravelLeg

CALL_MIN = 5
MIN_SERVICE_BEFORE_CLOSE = {ServiceType.food: 15, ServiceType.emergency_housing: 0, ServiceType.long_term_assistance: 30}
DWELL_MIN = {ServiceType.food: 30, ServiceType.emergency_housing: 0, ServiceType.long_term_assistance: 45}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Visit:
    resource: Resource
    arrival: datetime
    departure: datetime
    leg: Optional[TravelLeg]
    from_node: str
    slack_min: int
    day_label: str = "tonight"
    warnings: list[str] = field(default_factory=list)
    penalty: float = 0.0


@dataclass
class SearchResult:
    visits: list[Visit]
    score: float
    total_cost: float
    total_travel_min: int
    unmet: list[ServiceType]
    rejections: dict[str, str]
    call_first: Optional[Resource] = None
    feasible: bool = True
    covered: dict[ServiceType, Resource] = field(default_factory=dict)


def local_time(value: datetime) -> datetime:
    return value.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None) if value.tzinfo else value


def _deadline(need: Need, now: datetime, uc: UserConstraints) -> datetime:
    if need.deadline == "custom":
        return local_time(uc.constraints.custom_deadline) if uc.constraints.custom_deadline else now
    if need.deadline == "within_24_hours":
        return now + timedelta(hours=24)
    days = {"tonight": 0, "tomorrow": 1, "this_week": 7}.get(need.deadline, 0)
    return (now + timedelta(days=days)).replace(hour=23, minute=59)


def _arrival_check(r: Resource, arrival: datetime) -> Optional[str]:
    win = window_containing(r, arrival)
    if not win:
        return f"closed at {fmt(arrival)}"
    deadline = intake_deadline_for(r, win[0])
    if deadline and arrival > deadline:
        return f"intake closes {fmt(deadline)}, would arrive {fmt(arrival)}"
    if win[1] - arrival < timedelta(minutes=MIN_SERVICE_BEFORE_CLOSE[r.service]):
        return f"closes {fmt(win[1])}, would arrive {fmt(arrival)}"
    return None


def _slack(r: Resource, arrival: datetime) -> int:
    win = window_containing(r, arrival)
    if not win:
        return 0
    return int(((intake_deadline_for(r, win[0]) or win[1]) - arrival).total_seconds() // 60)


def _appointment(r: Resource, earliest: datetime, end: datetime) -> tuple[Optional[datetime], str]:
    arrival = earliest
    reason = "no opening before your deadline"
    for _ in range(10):
        if arrival > end:
            return None, reason
        problem = _arrival_check(r, arrival)
        if problem is None:
            return arrival, ""
        reason = problem
        win = window_containing(r, arrival)
        after = win[1] if win else arrival
        nxt = next_opening(r, after, within_days=7)
        if not nxt or nxt[0] > end:
            return None, reason
        arrival = nxt[0] + timedelta(minutes=5)
    return None, reason


def _score(visits: list[Visit], cost: float, travel: int, uc: UserConstraints) -> float:
    penalty = min(sum(v.penalty for v in visits), 0.3)
    slack = min((v.slack_min for v in visits), default=0)
    score = 1 - 0.4 * min(travel / 120, 1) - 0.15 * cost / max(uc.constraints.budget_usd or 10, 1) - penalty
    score += 0.05 * min(slack / 30, 1)
    for v in visits:
        if v.resource.service == ServiceType.long_term_assistance:
            score -= 0.008 * len(v.resource.eligibility.required_documents)
            if "id_replacement" in v.resource.tags:
                score += 0.06 if uc.constraints.has_id is False else -0.08
    return round(score, 5)


def search(g: nx.DiGraph, eligible: list[Resource], uc: UserConstraints, now: datetime,
           warnings: dict[str, list[str]], penalties: dict[str, float], transit,
           strategy: Strategy = "recommended") -> SearchResult:
    needs = list({n.type: n for n in uc.needs}.values())
    needs.sort(key=lambda n: (n.deadline in ("tomorrow", "this_week"),
                              n.type == ServiceType.emergency_housing, PRIORITY_RANK[n.priority]))
    pools = [[r for r in eligible if r.service == n.type] + [None] for n in needs]
    rejections: dict[str, str] = {}
    best_key = None
    best_visits: list[Visit] = []
    best_cost, best_travel, best_score = 0.0, 0, 0.0
    best_unmet = [n.type for n in needs]
    best_call = None
    best_covered: dict[ServiceType, Resource] = {}
    feasible_ids: set[str] = set()

    def consider(visits, cost, travel, missing, call):
        nonlocal best_key, best_visits, best_cost, best_travel, best_score, best_unmet, best_call, best_covered
        covered: dict[ServiceType, Resource] = {}
        if ServiceType.food in missing:
            feeder = next((v.resource for v in visits if v.resource.service == ServiceType.emergency_housing
                           and "meals_included" in v.resource.tags and v.day_label == "tonight"), None)
            if feeder is not None:
                covered[ServiceType.food] = feeder
                missing = [m for m in missing if m != ServiceType.food]
        missing_rank = tuple(sum(1 for n in needs if n.type in missing and n.priority == p)
                             for p in ("high", "medium", "low"))
        missing_rank += tuple(int(n.type in missing) for n in sorted(
            needs, key=lambda n: (PRIORITY_RANK[n.priority], n.type != ServiceType.emergency_housing)))
        score = _score(visits, cost, travel, uc)
        arrival = next((v.arrival.timestamp() for v in visits if v.resource.service == ServiceType.emergency_housing),
                       visits[-1].arrival.timestamp() if visits else 0)
        objective = {"recommended": (-score, cost, travel),
                     "fastest": (travel, arrival, cost),
                     "lowest_cost": (cost, travel, -score)}[strategy]
        key = missing_rank + objective
        if best_key is None or key < best_key:
            best_key, best_visits = key, visits
            best_cost, best_travel, best_score, best_unmet, best_call = cost, travel, score, missing, call
            best_covered = covered

    def schedule(pairs, index, loc, t, cost, travel, visits, missing, call):
        if index == len(pairs):
            consider(visits, cost, travel, missing, call)
            return
        need, r = pairs[index]
        if r is None:
            schedule(pairs, index + 1, loc, t, cost, travel, visits, missing + [need.type], call)
            return
        if not g.has_edge(loc, r.id):
            rejections.setdefault(r.id, "no route fits your transportation or walking limits")
            return
        ready = t
        if need.deadline == "tomorrow" or (need.type == ServiceType.long_term_assistance and visits and
                                           any(v.resource.service == ServiceType.emergency_housing for v in visits)):
            ready = max(ready, (now + timedelta(days=1)).replace(hour=7, minute=0))
        for leg in g[loc][r.id]["options"]:
            next_cost = round(cost + leg.cost_usd + r.cost, 2)
            if uc.constraints.budget_usd is not None and next_cost > uc.constraints.budget_usd:
                rejections.setdefault(r.id, "travel and service fees exceed your remaining budget")
                continue
            earliest = ready + timedelta(minutes=leg.duration_min)
            arrival, reason = _appointment(r, earliest, _deadline(need, now, uc))
            if arrival is None:
                rejections.setdefault(r.id, reason)
                continue
            day_offset = (arrival.date() - now.date()).days
            day = "tonight" if day_offset == 0 else "tomorrow" if day_offset == 1 else "later"
            vw = list(warnings.get(r.id, []))
            if "step_free" in uc.constraints.accessibility and leg.mode == "bus":
                vw.append("Step-free access is seeded for this demo; confirm vehicle and stop accessibility")
            penalty = penalties.get(r.id, 0.0)
            if leg.mode == "walk" and leg.long_walk:
                vw.append(f"Long walk: {leg.distance_km:.1f} km, about {leg.duration_min} min on foot. Tell us below if that is too far.")
                penalty += 0.1
            visit = Visit(r, arrival, arrival + timedelta(minutes=DWELL_MIN[r.service]), leg, loc,
                          _slack(r, arrival), day, vw, penalty)
            feasible_ids.add(r.id)
            schedule(pairs, index + 1, r.id, visit.departure, next_cost,
                     travel + leg.duration_min, visits + [visit], missing, call)

    for combo in itertools.product(*pools):
        pairs = list(zip(needs, combo))
        housing = next((r for r in combo if r and r.service == ServiceType.emergency_housing and r.phone), None)
        schedule(pairs, 0, ORIGIN, now + timedelta(minutes=CALL_MIN if housing else 0), 0.0, 0, [], [], housing)
    for rid in feasible_ids:
        rejections.pop(rid, None)
    return SearchResult(best_visits, best_score, best_cost, best_travel, best_unmet, rejections,
                        best_call, bool(best_visits) and not best_unmet, best_covered)
