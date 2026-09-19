import type { Constraints, Need, UserConstraints } from "./types";
export const NEIGHBORHOODS: Record<
  string,
  {
    lat: number;
    lng: number;
  }
> = {
  "Lexington Market": { lat: 39.291, lng: -76.6215 },
  "Mount Vernon": { lat: 39.2975, lng: -76.615 },
  "Charles Village": { lat: 39.32, lng: -76.616 },
  "Patterson Park": { lat: 39.2935, lng: -76.581 },
  "Federal Hill": { lat: 39.279, lng: -76.611 },
  Brooklyn: { lat: 39.24, lng: -76.605 },
};
export const TRANSPORT: Record<Constraints["transport"], string> = {
  no_vehicle: "No vehicle · bus or walk",
  public_transit: "Public transit + walking",
  walking: "Walking only",
  rideshare: "Rideshare",
  own_vehicle: "Own vehicle",
};
export const ACCESSIBILITY = {
  step_free: "Step-free access",
  limited_walking: "Limited walking",
  hearing_support: "Hearing support",
} as const;
export const DEFAULT_CONSTRAINTS: Constraints = {
  age: null,
  budget_usd: null,
  has_car: false,
  has_id: null,
  family_size: 1,
  gender: null,
  children: false,
  pets: false,
  accessibility: [],
  transport: "no_vehicle",
  transportation_needed: false,
  location_label: "Lexington Market",
  current_location: NEIGHBORHOODS["Lexington Market"],
  start_time: null,
  custom_deadline: null,
};
export function needFor(type: Need["type"]): Need {
  return {
    type,
    priority: type === "long_term_assistance" ? "low" : "high",
    deadline: type === "long_term_assistance" ? "tomorrow" : "tonight",
  };
}
export function emptyConstraints(): UserConstraints {
  return {
    needs: [],
    constraints: { ...DEFAULT_CONSTRAINTS },
    raw_text: "",
    extraction_source: "fallback",
  };
}
