from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from .models import LatLng, Plan, Resource, ResourceStatus, TransitData, TransitRoute

DATA_DIR = Path(__file__).parent / "data"
DATASETS = {"baltimore": "resources.json", "demo": "resources.demo.json"}


def default_dataset() -> str:
    return os.environ.get("LIGHTHOUSE_DATASET", "baltimore")


class Store:
    def __init__(self) -> None:
        self.resources: dict[str, Resource] = {}
        self.transit: TransitData
        self.plans: dict[str, Plan] = {}
        self.default_origin = LatLng(lat=39.2910, lng=-76.6215)
        self._initial_status: dict[str, ResourceStatus] = {}
        self.load()

    def load(self, dataset: Optional[str] = None) -> None:
        self.dataset = dataset or default_dataset()
        raw = json.loads((DATA_DIR / DATASETS[self.dataset]).read_text())
        self.meta = raw.get("meta", {})
        origin = raw.get("meta", {}).get("default_origin")
        if origin:
            self.default_origin = LatLng(lat=origin["lat"], lng=origin["lng"])
        self.resources = {r["id"]: Resource.model_validate(r) for r in raw["resources"]}
        self._initial_status = {rid: r.status for rid, r in self.resources.items()}
        self._initial_capacity = {rid: r.capacity for rid, r in self.resources.items()}
        self.transit = TransitData.model_validate(json.loads((DATA_DIR / "transit.json").read_text()))

    def all_resources(self) -> list[Resource]:
        return list(self.resources.values())

    def get(self, rid: str) -> Optional[Resource]:
        return self.resources.get(rid)

    def set_status(self, rid: str, status: ResourceStatus, capacity: Optional[int] = None) -> Resource:
        r = self.resources[rid]
        r.status = status
        if capacity is not None:
            r.capacity = capacity
        return r

    def reset_status(self) -> None:
        for rid, st in self._initial_status.items():
            self.resources[rid].status = st
            self.resources[rid].capacity = self._initial_capacity[rid]
        self.reset_delays()

    def route(self, route_id: str) -> Optional[TransitRoute]:
        return next((r for r in self.transit.routes if r.id == route_id), None)

    def set_delay(self, route_id: str, minutes: int) -> TransitRoute:
        route = self.route(route_id)
        if route is None:
            raise KeyError(route_id)
        route.delay_min = minutes
        return route

    def reset_delays(self) -> None:
        for route in self.transit.routes:
            route.delay_min = 0

    def save_plan(self, plan: Plan) -> None:
        self.plans[plan.plan_id] = deepcopy(plan)

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self.plans.get(plan_id)


store = Store()
