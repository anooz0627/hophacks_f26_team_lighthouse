import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import UnroutedResources from "@/components/UnroutedResources";
import PlanComparison from "@/components/PlanComparison";
import { emptyConstraints } from "@/lib/constraints";
import type { Plan, Resource } from "@/lib/types";
import data from "../../backend/app/data/resources.json";

it("shows contact options without inventing a route and links directions from the chosen origin", () => {
  const record = data.resources.find((r) => r.id === "whrc")!;
  const resource: Resource = {
    id: record.id,
    name: record.name,
    service: "emergency_housing",
    description: record.description,
    address: record.address,
    lat: record.lat,
    lng: record.lng,
    phone: record.phone,
    hours: record.hours,
    intake_deadline: record.intake_deadline ?? null,
    eligibility: {
      min_age: 18,
      max_age: null,
      requires_id: false,
      gender: null,
      families_ok: false,
      children_ok: false,
      pets_ok: null,
      accessibility: [],
      required_documents: [],
    },
    cost: 0,
    capacity: null,
    status: "available",
    website_url: null,
    source_url: null,
    simulated: false,
    last_verified: null,
    notes: "",
    tags: [],
  };
  const constraints = emptyConstraints();
  constraints.constraints.current_location = { lat: 39.329, lng: -76.62 };
  const plan: Plan = {
    plan_id: "no-route",
    strategy: "recommended",
    tradeoff: "",
    created_at: "2026-09-20T01:00",
    now: "2026-09-20T01:00",
    constraints,
    steps: [],
    resource_ids: [],
    total_cost_usd: 0,
    total_travel_min: 0,
    score: 0,
    feasible: false,
    unmet_needs: ["emergency_housing"],
    explanation: "",
    rejected: [],
    graph: { nodes: [], edges: [] },
    unrouted_resources: [
      {
        resource_id: resource.id,
        distance_km: 4,
        reason: "Travel is unconfirmed",
        warnings: ["Photo ID required — confirm you have one"],
      },
    ],
  };
  const editLocation = vi.fn();
  const details = vi.fn();
  render(
    <>
      <PlanComparison
        plans={[plan]}
        selected={plan.plan_id}
        onSelect={() => {}}
        note=""
      />
      <UnroutedResources
        plan={plan}
        resources={[resource]}
        onDetails={details}
        onEditLocation={editLocation}
        onEditDetails={() => {}}
      />
    </>,
  );
  expect(screen.getByText("Places that may help.")).toBeTruthy();
  expect(screen.getByText("Route confirmation needed")).toBeTruthy();
  expect(screen.getByText(resource.name)).toBeTruthy();
  expect(
    screen.getByText("Photo ID required — confirm you have one"),
  ).toBeTruthy();
  const link = screen.getByRole("link", {
    name: "Check route in Google Maps",
  }) as HTMLAnchorElement;
  const url = new URL(link.href);
  expect(url.searchParams.get("origin")).toBe("39.329,-76.62");
  expect(url.searchParams.get("travelmode")).toBe("transit");
  expect(url.searchParams.get("destination")).toBe(resource.address);
  fireEvent.click(
    screen.getByRole("button", { name: "Change starting location" }),
  );
  expect(editLocation).toHaveBeenCalledTimes(1);
  fireEvent.click(
    screen.getByRole("button", { name: "Hours, requirements & source" }),
  );
  expect(details).toHaveBeenCalledWith(resource);
});
