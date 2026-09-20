from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints


class ServiceType(str, Enum):
    emergency_housing = "emergency_housing"
    food = "food"
    long_term_assistance = "long_term_assistance"


class ResourceStatus(str, Enum):
    available = "available"
    full = "full"
    closed = "closed"
    unavailable = "unavailable"
    delayed = "delayed"


Priority = Literal["high", "medium", "low"]
Deadline = Literal["tonight", "tomorrow", "this_week", "within_24_hours", "custom"]
Strategy = Literal["recommended", "fastest", "lowest_cost"]


class HoursWindow(BaseModel):
    days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    open: str
    close: str


class Eligibility(BaseModel):
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    requires_id: bool = False
    gender: Optional[Literal["male", "female"]] = None
    families_ok: bool = True
    children_ok: Optional[bool] = None
    pets_ok: Optional[bool] = None
    accessibility: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)


class Resource(BaseModel):
    id: str
    name: str
    service: ServiceType
    description: str = ""
    address: str = ""
    lat: float
    lng: float
    phone: Optional[str] = None
    hours: list[HoursWindow]
    intake_deadline: Optional[str] = None
    eligibility: Eligibility = Field(default_factory=Eligibility)
    cost: float = 0.0
    capacity: Optional[int] = None
    status: ResourceStatus = ResourceStatus.available
    website_url: Optional[str] = None
    source_url: Optional[str] = None
    simulated: bool = True
    last_verified: Optional[str] = None
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class Stop(BaseModel):
    name: str
    lat: float
    lng: float


class TransitRoute(BaseModel):
    id: str
    name: str
    fare: float
    headway_min: int
    avg_speed_kmh: float = 22.0
    stops: list[Stop]


class TransitData(BaseModel):
    walk_speed_kmh: float = 4.5
    max_walk_km: float = 2.5
    routes: list[TransitRoute]


class Need(BaseModel):
    type: ServiceType
    priority: Priority = "high"
    deadline: Deadline = "tonight"


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Constraints(BaseModel):
    age: Optional[int] = Field(default=None, ge=0, le=120)
    budget_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    has_car: bool = False
    has_id: Optional[bool] = None
    family_size: int = Field(default=1, ge=1, le=20)
    children: bool = False
    pets: bool = False
    accessibility: list[Literal["step_free", "limited_walking", "hearing_support"]] = Field(default_factory=list)
    transport: Literal["no_vehicle", "public_transit", "walking", "rideshare", "own_vehicle"] = "no_vehicle"
    transportation_needed: bool = False
    location_label: str = "Lexington Market"
    custom_deadline: Optional[datetime] = None
    gender: Optional[Literal["male", "female"]] = None
    current_location: Optional[LatLng] = None
    start_time: Optional[datetime] = None


class UserConstraints(BaseModel):
    needs: list[Need]
    constraints: Constraints
    raw_text: str = ""
    extraction_source: Literal["llm", "fallback"] = "fallback"


StepType = Literal["call", "travel", "visit", "note"]


class PlanStep(BaseModel):
    order: int
    type: StepType
    time: str
    time_iso: str
    day_label: Literal["tonight", "tomorrow", "later"] = "tonight"
    title: str
    detail: str = ""
    resource_id: Optional[str] = None
    route_id: Optional[str] = None
    mode: Optional[Literal["walk", "bus", "car", "rideshare"]] = None
    duration_min: Optional[int] = None
    cost_usd: float = 0.0
    lat: Optional[float] = None
    lng: Optional[float] = None
    polyline: list[list[float]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    bring: list[str] = Field(default_factory=list)


class RejectedResource(BaseModel):
    resource_id: str
    name: str
    service: ServiceType
    reason: str


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["origin", "resource", "need"]
    service: Optional[ServiceType] = None
    selected: bool = False
    eligible: bool = True


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: Literal["provides", "reachable_by", "requires"]
    label: str = ""
    selected: bool = False


class PlanGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Plan(BaseModel):
    plan_id: str
    strategy: Strategy = "recommended"
    tradeoff: str = ""
    created_at: str
    now: str
    constraints: UserConstraints
    steps: list[PlanStep]
    resource_ids: list[str]
    total_cost_usd: float
    total_travel_min: int
    score: float
    feasible: bool
    unmet_needs: list[ServiceType] = Field(default_factory=list)
    explanation: str = ""
    rejected: list[RejectedResource] = Field(default_factory=list)
    graph: PlanGraph


class PlanDiff(BaseModel):
    removed_resource_ids: list[str]
    added_resource_ids: list[str]
    trigger: Optional[str] = None
    travel_delta_min: int = 0
    cost_delta_usd: float = 0
    feasible: bool = True


SituationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class PlanRequest(BaseModel):
    text: SituationText
    current_location: Optional[LatLng] = None
    now: Optional[datetime] = None


class ExtractRequest(BaseModel):
    text: SituationText


class ReplanRequest(BaseModel):
    plan_id: str
    now: Optional[datetime] = None


class ReplanResponse(BaseModel):
    plan: Plan
    previous_plan_id: str
    diff: PlanDiff


class PlanBundleRequest(BaseModel):
    constraints: UserConstraints
    now: Optional[datetime] = None
    previous_plan_id: Optional[str] = None


class PlanBundle(BaseModel):
    plans: list[Plan]
    alternatives_note: str = ""
    diff: Optional[PlanDiff] = None


class StatusUpdate(BaseModel):
    status: ResourceStatus
    capacity: Optional[int] = Field(default=None, ge=0)


class Health(BaseModel):
    ok: bool
    llm: bool
    voice: bool = False
    resources: int
