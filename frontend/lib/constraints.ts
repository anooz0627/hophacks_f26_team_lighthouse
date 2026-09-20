import type { Constraints, Need, UserConstraints } from "./types";
export const TRANSPORT: Record<Constraints["transport"], string> = {
  no_vehicle: "No vehicle · bus or walk",
  public_transit: "Public transit + walking",
  walking: "Walking only",
  rideshare: "Rideshare",
  own_vehicle: "Own vehicle",
};
export const ACCESSIBILITY = {
  step_free: "I need step-free access",
  limited_walking: "I need shorter walks",
  hearing_support: "I need hearing support",
} as const;
export const SUPPORT_DETAILS = {
  step_free: "Only include places with confirmed step-free access.",
  limited_walking:
    "Limit walking-only trips to 400 m and walks to bus stops to 8 minutes total.",
  hearing_support: "Only include places with confirmed hearing support.",
} as const;
export const GENDERS = {
  female: "Woman",
  male: "Man",
  non_binary: "Non-binary",
  self_describe: "Self-describe",
  prefer_not_to_say: "Prefer not to say",
} as const;
export const DEFAULT_CONSTRAINTS: Constraints = {
  age: null,
  budget_usd: null,
  has_car: false,
  has_id: null,
  family_size: 1,
  gender: null,
  children: false,
  other_household_members: false,
  pets: false,
  accessibility: [],
  transport: "no_vehicle",
  transportation_needed: false,
  location_label: "Current location",
  current_location: null,
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
