"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import {
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import type { Plan, PlanStep, Resource, TravelMode } from "@/lib/types";
import {
  MODE_LABEL,
  MODE_STYLE,
  ORIGIN_COLOR,
  SERVICE_COLOR,
  SERVICE_LABEL,
  STATUS_LABEL,
} from "@/lib/format";

type Point = [number, number];

const DEFAULT_CENTER: Point = [39.291, -76.6215];
const DEFAULT_ZOOM = 13;

interface Props {
  plan: Plan | null;
  resources: Resource[];
  previousPlan: Plan | null;
}

function makeIcon(opts: {
  color: string;
  size: number;
  opacity: number;
  label?: string;
  ring?: boolean;
}): L.DivIcon {
  const { color, size, opacity, label = "", ring = false } = opts;
  const shadow = ring
    ? "0 1px 4px rgba(0,0,0,.35), 0 0 0 4px rgba(17,24,39,.18)"
    : "0 1px 4px rgba(0,0,0,.35)";
  const fontSize = Math.max(10, Math.round(size * 0.5));
  const html =
    `<div style="width:${size}px;height:${size}px;border-radius:9999px;background:${color};opacity:${opacity};` +
    `border:2px solid #fff;box-shadow:${shadow};display:flex;align-items:center;justify-content:center;` +
    `color:#fff;font:700 ${fontSize}px/1 system-ui,sans-serif;box-sizing:border-box">${label}</div>`;
  return L.divIcon({
    html,
    className: "aidgraph-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    tooltipAnchor: [0, -size / 2],
  });
}

function toPoints(polyline: number[][]): Point[] {
  return polyline.filter((p) => p.length >= 2).map((p) => [p[0], p[1]]);
}

function travelSteps(plan: Plan | null): PlanStep[] {
  if (!plan) return [];
  return plan.steps.filter((s) => s.type === "travel" && s.polyline.length >= 2);
}

function FitBounds({ points }: { points: Point[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
  }, [map, points]);
  return null;
}

export default function PlanMap({ plan, resources, previousPlan }: Props) {
  const origin = plan?.constraints.constraints.current_location ?? null;
  const inPlan = useMemo(() => new Set(plan?.resource_ids ?? []), [plan]);

  const visitOrder = useMemo(() => {
    const order = new Map<string, number>();
    if (!plan) return order;
    for (const step of plan.steps) {
      if (
        step.type === "visit" &&
        step.resource_id &&
        !order.has(step.resource_id)
      ) {
        order.set(step.resource_id, order.size + 1);
      }
    }
    return order;
  }, [plan]);

  const markers = useMemo(
    () =>
      resources.map((r) => {
        const selected = inPlan.has(r.id);
        const order = visitOrder.get(r.id);
        const icon = makeIcon({
          color: SERVICE_COLOR[r.service],
          size: selected ? 28 : 12,
          opacity: selected ? 1 : 0.4,
          label: selected && order ? String(order) : "",
        });
        return { resource: r, icon, selected };
      }),
    [resources, inPlan, visitOrder],
  );

  const originIcon = useMemo(
    () => makeIcon({ color: ORIGIN_COLOR, size: 20, opacity: 1, ring: true }),
    [],
  );

  const routes = useMemo(() => travelSteps(plan), [plan]);
  const ghostRoutes = useMemo(() => travelSteps(previousPlan), [previousPlan]);

  const fitPoints = useMemo<Point[]>(() => {
    if (plan) {
      const pts: Point[] = [];
      if (origin) pts.push([origin.lat, origin.lng]);
      for (const step of plan.steps) {
        if (step.lat !== null && step.lng !== null)
          pts.push([step.lat, step.lng]);
        pts.push(...toPoints(step.polyline));
      }
      return pts;
    }
    return resources.map((r) => [r.lat, r.lng]);
  }, [plan, origin, resources]);

  return (
    <div className="relative isolate z-0 h-[360px] w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 lg:h-[440px]">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        scrollWheelZoom={false}
        className="h-full w-full"
        style={{ background: "#e2e8f0" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {ghostRoutes.map((step) => (
          <Polyline
            key={`ghost-${previousPlan?.plan_id}-${step.order}`}
            positions={toPoints(step.polyline)}
            pathOptions={{
              color: "#9ca3af",
              weight: 4,
              dashArray: "6 8",
              opacity: 0.8,
            }}
          />
        ))}

        {routes.map((step) => {
          const mode: TravelMode = step.mode ?? "bus";
          const style = MODE_STYLE[mode];
          return (
            <Polyline
              key={`${plan?.plan_id}-${step.order}`}
              positions={toPoints(step.polyline)}
              pathOptions={{
                color: style.color,
                weight: style.weight,
                dashArray: style.dashArray,
                opacity: 0.95,
              }}
            >
              <Tooltip sticky>
                {MODE_LABEL[mode]}
                {step.duration_min !== null ? ` · ~${step.duration_min} min` : ""}
              </Tooltip>
            </Polyline>
          );
        })}

        {markers.map(({ resource, icon, selected }) => (
          <Marker
            title={resource.name}
            alt={resource.name}
            key={resource.id}
            position={[resource.lat, resource.lng]}
            icon={icon}
            zIndexOffset={selected ? 500 : 0}
          >
            <Tooltip direction="top">
              <span className="font-semibold">{resource.name}</span>
              <br />
              {SERVICE_LABEL[resource.service]} · {STATUS_LABEL[resource.status]}
            </Tooltip>
          </Marker>
        ))}

        {origin && (
          <Marker
            title="Starting neighborhood"
            alt="Starting neighborhood"
            position={[origin.lat, origin.lng]}
            icon={originIcon}
            zIndexOffset={1000}
          >
            <Tooltip direction="top" permanent>
              <span className="font-semibold">Start (you)</span>
            </Tooltip>
          </Marker>
        )}

        <FitBounds points={fitPoints} />
      </MapContainer>

      <div className="pointer-events-none absolute bottom-3 left-3 z-[1100] rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow-sm">
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          <LegendDot color={ORIGIN_COLOR} label="You" />
          <LegendDot color={SERVICE_COLOR.emergency_housing} label="Housing" />
          <LegendDot color={SERVICE_COLOR.food} label="Food" />
          <LegendDot
            color={SERVICE_COLOR.long_term_assistance}
            label="Long-term"
          />
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
          <LegendLine color={MODE_STYLE.bus.color} label="Bus" />
          <LegendLine color={MODE_STYLE.walk.color} label="Walk" dashed />
          <LegendLine color={MODE_STYLE.car.color} label="Drive" />
        </div>
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-3 w-3 rounded-full border border-white shadow"
        style={{ background: color }}
        aria-hidden
      />
      {label}
    </span>
  );
}

function LegendLine({
  color,
  label,
  dashed = false,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block w-5"
        style={{ borderTop: `3px ${dashed ? "dashed" : "solid"} ${color}` }}
        aria-hidden
      />
      {label}
    </span>
  );
}
