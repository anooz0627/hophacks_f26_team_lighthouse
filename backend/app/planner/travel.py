from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..models import Constraints, LatLng, TransitData

Point = tuple[float, float]

MAX_WALK_TO_STOP_KM = 1.0
TRANSFER_RADIUS_KM = 0.15
TRANSFER_PENALTY_MIN = 3
CAR_SPEED_KMH = 30.0
STREET_FACTOR = 1.25


@dataclass
class TravelLeg:
    mode: str
    duration_min: int
    cost_usd: float
    polyline: list[list[float]]
    route_id: Optional[str] = None
    route_name: Optional[str] = None
    board_stop: Optional[str] = None
    alight_stop: Optional[str] = None
    walk_to_stop_min: int = 0
    wait_min: int = 0
    ride_min: int = 0
    walk_from_stop_min: int = 0
    distance_km: float = 0.0
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if self.mode == "walk":
            return f"Walk {self.distance_km:.1f} km · ~{self.duration_min} min"
        if self.mode == "rideshare":
            return f"Rideshare estimate · ~{self.duration_min} min · ${self.cost_usd:.2f}; confirm fare and accessible vehicle"
        if self.mode == "car":
            return f"Drive {self.distance_km:.1f} km · ~{self.duration_min} min"
        transfer = f" {self.notes[0]}." if self.notes else ""
        return (
            f"Walk to {self.board_stop} ({self.walk_to_stop_min} min), "
            f"ride {self.route_name} to {self.alight_stop} (~{self.ride_min} min).{transfer} "
            f"Walk {self.walk_from_stop_min} min · ${self.cost_usd:.2f}"
        )


def haversine_km(a: Point, b: Point) -> float:
    r = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _minutes(km: float, kmh: float) -> int:
    return max(1, int(math.ceil(km / kmh * 60)))


def walk_leg(a: Point, b: Point, transit: TransitData, force: bool = False) -> Optional[TravelLeg]:
    km = haversine_km(a, b) * STREET_FACTOR
    if km > transit.max_walk_km and not force:
        return None
    return TravelLeg(mode="walk", duration_min=_minutes(km, transit.walk_speed_kmh), cost_usd=0.0,
                     polyline=[[a[0], a[1]], [b[0], b[1]]], distance_km=km)


def car_leg(a: Point, b: Point) -> TravelLeg:
    km = haversine_km(a, b) * 1.3
    return TravelLeg(mode="car", duration_min=_minutes(km, CAR_SPEED_KMH) + 5, cost_usd=0.0,
                     polyline=[[a[0], a[1]], [b[0], b[1]]], distance_km=km)


def bus_legs(a: Point, b: Point, transit: TransitData) -> list[TravelLeg]:
    legs: list[TravelLeg] = []
    for route in transit.routes:
        stops = route.stops
        ia = min(range(len(stops)), key=lambda i: haversine_km(a, (stops[i].lat, stops[i].lng)))
        ib = min(range(len(stops)), key=lambda i: haversine_km(b, (stops[i].lat, stops[i].lng)))
        if ia == ib:
            continue
        da = haversine_km(a, (stops[ia].lat, stops[ia].lng)) * STREET_FACTOR
        db = haversine_km(b, (stops[ib].lat, stops[ib].lng)) * STREET_FACTOR
        if da > MAX_WALK_TO_STOP_KM or db > MAX_WALK_TO_STOP_KM:
            continue
        lo, hi = sorted((ia, ib))
        ride_km = sum(
            haversine_km((stops[i].lat, stops[i].lng), (stops[i + 1].lat, stops[i + 1].lng))
            for i in range(lo, hi)
        ) * 1.2
        ride_min = _minutes(ride_km, route.avg_speed_kmh) + (hi - lo)
        w1 = _minutes(da, transit.walk_speed_kmh)
        w2 = _minutes(db, transit.walk_speed_kmh)
        wait = route.headway_min // 2
        seq = range(ia, ib + 1) if ia < ib else range(ia, ib - 1, -1)
        poly = [[a[0], a[1]]] + [[stops[i].lat, stops[i].lng] for i in seq] + [[b[0], b[1]]]
        legs.append(TravelLeg(
            mode="bus", duration_min=w1 + wait + ride_min + w2, cost_usd=route.fare, polyline=poly,
            route_id=route.id, route_name=route.name, board_stop=stops[ia].name, alight_stop=stops[ib].name,
            walk_to_stop_min=w1, wait_min=wait, ride_min=ride_min, walk_from_stop_min=w2,
            distance_km=da + ride_km + db,
        ))
    return legs


def _ride(route, ia: int, ib: int) -> tuple[float, int, list[list[float]]]:
    stops = route.stops
    lo, hi = sorted((ia, ib))
    km = sum(haversine_km((stops[i].lat, stops[i].lng), (stops[i + 1].lat, stops[i + 1].lng))
             for i in range(lo, hi)) * 1.2
    mins = _minutes(km, route.avg_speed_kmh) + (hi - lo)
    seq = range(ia, ib + 1) if ia < ib else range(ia, ib - 1, -1)
    return km, mins, [[stops[i].lat, stops[i].lng] for i in seq]


def transfer_legs(a: Point, b: Point, transit: TransitData) -> list[TravelLeg]:
    legs: list[TravelLeg] = []
    routes = transit.routes
    for r1 in routes:
        s1 = r1.stops
        ia = min(range(len(s1)), key=lambda i: haversine_km(a, (s1[i].lat, s1[i].lng)))
        da = haversine_km(a, (s1[ia].lat, s1[ia].lng)) * STREET_FACTOR
        if da > MAX_WALK_TO_STOP_KM:
            continue
        for r2 in routes:
            if r2.id == r1.id:
                continue
            s2 = r2.stops
            ib = min(range(len(s2)), key=lambda i: haversine_km(b, (s2[i].lat, s2[i].lng)))
            db = haversine_km(b, (s2[ib].lat, s2[ib].lng)) * STREET_FACTOR
            if db > MAX_WALK_TO_STOP_KM:
                continue
            for x1, st1 in enumerate(s1):
                if x1 == ia:
                    continue
                for x2, st2 in enumerate(s2):
                    if x2 == ib or haversine_km((st1.lat, st1.lng), (st2.lat, st2.lng)) > TRANSFER_RADIUS_KM:
                        continue
                    km1, m1, poly1 = _ride(r1, ia, x1)
                    km2, m2, poly2 = _ride(r2, x2, ib)
                    w1 = _minutes(da, transit.walk_speed_kmh)
                    w2 = _minutes(db, transit.walk_speed_kmh)
                    wait = r1.headway_min // 2 + r2.headway_min // 2 + TRANSFER_PENALTY_MIN
                    poly = [[a[0], a[1]]] + poly1 + poly2 + [[b[0], b[1]]]
                    legs.append(TravelLeg(
                        mode="bus", duration_min=w1 + wait + m1 + m2 + w2, cost_usd=r1.fare + r2.fare, polyline=poly,
                        route_id=f"{r1.id}+{r2.id}", route_name=f"{r1.name} → {r2.name}",
                        board_stop=s1[ia].name, alight_stop=s2[ib].name, walk_to_stop_min=w1, wait_min=wait,
                        ride_min=m1 + m2, walk_from_stop_min=w2, distance_km=da + km1 + km2 + db,
                        notes=[f"Transfer at {st1.name}"]))
    return legs


def travel_options(a: Point, b: Point, constraints: Constraints, transit: TransitData,
                   budget_left: Optional[float] = None) -> list[TravelLeg]:
    mode = constraints.transport
    if mode == "own_vehicle" or (mode == "no_vehicle" and constraints.has_car):
        options = [car_leg(a, b)]
    elif mode == "rideshare":
        leg = car_leg(a, b)
        leg.mode = "rideshare"
        leg.cost_usd = round((5 + leg.distance_km * 1.8) * math.ceil(constraints.family_size / 4), 2)
        options = [leg]
    else:
        options = []
        limit = 0.4 if "limited_walking" in constraints.accessibility else transit.max_walk_km
        walk = walk_leg(a, b, transit.model_copy(update={"max_walk_km": limit}))
        if walk:
            options.append(walk)
        if mode != "walking":
            buses = bus_legs(a, b, transit) + transfer_legs(a, b, transit)
            if "limited_walking" in constraints.accessibility:
                buses = [leg for leg in buses if leg.walk_to_stop_min + leg.walk_from_stop_min <= 8]
            for leg in buses:
                leg.cost_usd *= constraints.family_size
            if buses:
                by_cost = {}
                for leg in sorted(buses, key=lambda x: x.duration_min):
                    by_cost.setdefault(leg.cost_usd, leg)
                options.extend(by_cost.values())
    return [leg for leg in options if budget_left is None or leg.cost_usd <= budget_left]


def best_leg(a: Point, b: Point, constraints: Constraints, transit: TransitData,
             budget_left: Optional[float] = None) -> Optional[TravelLeg]:
    options = travel_options(a, b, constraints, transit, budget_left)
    return min(options, key=lambda leg: (leg.duration_min, leg.cost_usd), default=None)


def to_point(p: LatLng) -> Point:
    return (p.lat, p.lng)
