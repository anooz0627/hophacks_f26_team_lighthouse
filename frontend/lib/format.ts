import type {
  Deadline,
  PlanStep,
  Priority,
  ResourceStatus,
  ServiceType,
  TravelMode,
} from "./types";
export const SERVICE_LABEL: Record<ServiceType, string> = {
  emergency_housing: "Emergency housing",
  food: "Food",
  long_term_assistance: "Long-term assistance",
};
export const SERVICE_ICON: Record<ServiceType, string> = {
  emergency_housing: "🏠",
  food: "🍽️",
  long_term_assistance: "🏢",
};
export const SERVICE_COLOR: Record<ServiceType, string> = {
  emergency_housing: "#7c3aed",
  food: "#ea580c",
  long_term_assistance: "#0d9488",
};
export const SERVICE_CHIP: Record<ServiceType, string> = {
  emergency_housing: "border-violet-200 bg-violet-50 text-violet-900",
  food: "border-orange-200 bg-orange-50 text-orange-900",
  long_term_assistance: "border-teal-200 bg-teal-50 text-teal-900",
};
export const ORIGIN_COLOR = "#111827";
export const STATUS_OPTIONS: ResourceStatus[] = [
  "available",
  "full",
  "closed",
  "unavailable",
  "delayed",
];
export const STATUS_LABEL: Record<ResourceStatus, string> = {
  available: "Available",
  full: "Full",
  closed: "Closed",
  unavailable: "Temporarily unavailable",
  delayed: "Delayed",
};
export const STATUS_CHIP: Record<ResourceStatus, string> = {
  available: "bg-emerald-100 text-emerald-900",
  full: "bg-rose-100 text-rose-900",
  closed: "bg-slate-200 text-slate-800",
  unavailable: "bg-rose-100 text-rose-900",
  delayed: "bg-amber-100 text-amber-900",
};
export const PRIORITY_CHIP: Record<Priority, string> = {
  high: "bg-rose-100 text-rose-900",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-slate-100 text-slate-700",
};
export const DEADLINE_LABEL: Record<Deadline, string> = {
  tonight: "tonight",
  tomorrow: "tomorrow",
  this_week: "this week",
  within_24_hours: "within 24 hours",
  custom: "custom deadline",
};
export const MODE_LABEL: Record<TravelMode, string> = {
  bus: "Bus",
  walk: "Walk",
  car: "Drive",
  rideshare: "Rideshare",
};
export const MODE_ICON: Record<TravelMode, string> = {
  bus: "🚌",
  walk: "🚶",
  car: "🚗",
  rideshare: "🚗",
};
export const MODE_STYLE: Record<
  TravelMode,
  {
    color: string;
    weight: number;
    dashArray?: string;
  }
> = {
  bus: { color: "#2563eb", weight: 5 },
  walk: { color: "#6b7280", weight: 4, dashArray: "8 10" },
  car: { color: "#1f2937", weight: 5 },
  rideshare: { color: "#6d4cc4", weight: 5 },
};
export function demoNowIso(): string {
  return "2026-09-20T18:00:00";
}

export function timelineDayLabel(date: string, now: string): string {
  if (date === now.slice(0, 10)) return "Tonight";

  const tomorrow = new Date(`${now.slice(0, 10)}T12:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  if (date === tomorrow.toISOString().slice(0, 10)) return "Tomorrow";

  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", {
    timeZone: "UTC",
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

export function timeLabel(time: string): string {
  const [h, m] = time.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
}
export function formatUsd(amount: number): string {
  if (amount === 0) return "$0";
  return `$${amount.toFixed(2)}`;
}
export function stepIcon(step: PlanStep, service?: ServiceType): string {
  switch (step.type) {
    case "call":
      return "📞";
    case "travel":
      return step.mode ? MODE_ICON[step.mode] : "🚌";
    case "visit":
      return service ? SERVICE_ICON[service] : "📍";
    case "note":
      return "⚠️";
  }
}
