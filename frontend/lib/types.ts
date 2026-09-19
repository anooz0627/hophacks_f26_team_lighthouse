export type ServiceType = "emergency_housing" | "food" | "long_term_assistance";
export type ResourceStatus =
  | "available"
  | "full"
  | "closed"
  | "unavailable"
  | "delayed";
export type Priority = "high" | "medium" | "low";
export type Deadline =
  | "tonight"
  | "tomorrow"
  | "this_week"
  | "within_24_hours"
  | "custom";
export type Gender = "male" | "female";
export interface HoursWindow {
  days: string[];
  open: string;
  close: string;
}
export interface Eligibility {
  min_age: number | null;
  max_age: number | null;
  requires_id: boolean;
  gender: Gender | null;
  families_ok: boolean;
  children_ok: boolean | null;
  pets_ok: boolean | null;
  accessibility: string[];
  required_documents: string[];
}
export interface Resource {
  id: string;
  name: string;
  service: ServiceType;
  description: string;
  address: string;
  lat: number;
  lng: number;
  phone: string | null;
  hours: HoursWindow[];
  intake_deadline: string | null;
  eligibility: Eligibility;
  cost: number;
  capacity: number | null;
  status: ResourceStatus;
  website_url: string | null;
  simulated: boolean;
  source_url: string | null;
  last_verified: string | null;
  notes: string;
  tags: string[];
}
export interface Stop {
  name: string;
  lat: number;
  lng: number;
}
export interface TransitRoute {
  id: string;
  name: string;
  fare: number;
  headway_min: number;
  avg_speed_kmh: number;
  stops: Stop[];
}
export interface TransitData {
  walk_speed_kmh: number;
  max_walk_km: number;
  routes: TransitRoute[];
}
export interface Need {
  type: ServiceType;
  priority: Priority;
  deadline: Deadline;
}
export interface LatLng {
  lat: number;
  lng: number;
}
export interface Constraints {
  age: number | null;
  budget_usd: number | null;
  has_car: boolean;
  has_id: boolean | null;
  family_size: number;
  children: boolean;
  pets: boolean;
  accessibility: ("step_free" | "limited_walking" | "hearing_support")[];
  transport:
    | "no_vehicle"
    | "public_transit"
    | "walking"
    | "rideshare"
    | "own_vehicle";
  transportation_needed: boolean;
  location_label: string;
  custom_deadline: string | null;
  gender: Gender | null;
  current_location: LatLng | null;
  start_time: string | null;
}
export type ExtractionSource = "llm" | "fallback";
export interface UserConstraints {
  needs: Need[];
  constraints: Constraints;
  raw_text: string;
  extraction_source: ExtractionSource;
}
export type StepType = "call" | "travel" | "visit" | "note";
export type TravelMode = "walk" | "bus" | "car" | "rideshare";
export type DayLabel = "tonight" | "tomorrow" | "later";
export interface PlanStep {
  order: number;
  type: StepType;
  time: string;
  time_iso: string;
  day_label: DayLabel;
  title: string;
  detail: string;
  resource_id: string | null;
  route_id: string | null;
  mode: TravelMode | null;
  duration_min: number | null;
  cost_usd: number;
  lat: number | null;
  lng: number | null;
  polyline: number[][];
  warnings: string[];
  bring: string[];
}
export interface RejectedResource {
  resource_id: string;
  name: string;
  service: ServiceType;
  reason: string;
}
export type GraphNodeKind = "origin" | "resource" | "need";
export interface GraphNode {
  id: string;
  label: string;
  kind: GraphNodeKind;
  service: ServiceType | null;
  selected: boolean;
  eligible: boolean;
}
export type GraphEdgeKind = "provides" | "reachable_by" | "requires";
export interface GraphEdge {
  source: string;
  target: string;
  kind: GraphEdgeKind;
  label: string;
  selected: boolean;
}
export interface PlanGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
export type Strategy = "recommended" | "fastest" | "lowest_cost";
export interface Plan {
  strategy: Strategy;
  tradeoff: string;
  plan_id: string;
  created_at: string;
  now: string;
  constraints: UserConstraints;
  steps: PlanStep[];
  resource_ids: string[];
  total_cost_usd: number;
  total_travel_min: number;
  score: number;
  feasible: boolean;
  unmet_needs: ServiceType[];
  explanation: string;
  rejected: RejectedResource[];
  graph: PlanGraph;
}
export interface PlanDiff {
  removed_resource_ids: string[];
  added_resource_ids: string[];
  trigger: string | null;
  travel_delta_min: number;
  cost_delta_usd: number;
  feasible: boolean;
}
export interface PlanRequest {
  text: string;
  current_location?: LatLng;
  now?: string;
}
export interface ExtractRequest {
  text: string;
}
export interface ReplanRequest {
  plan_id: string;
  now?: string;
}
export interface ReplanResponse {
  plan: Plan;
  previous_plan_id: string;
  diff: PlanDiff;
}
export interface StatusUpdate {
  status: ResourceStatus;
  capacity?: number | null;
}
export interface Health {
  ok: boolean;
  llm: boolean;
  resources: number;
}
export interface PlanBundle {
  plans: Plan[];
  alternatives_note: string;
  diff: PlanDiff | null;
}
