import { API_BASE } from "@/lib/api";
import {
  SERVICE_LABEL,
  STATUS_LABEL,
  formatUsd,
  timeLabel,
} from "@/lib/format";
import { ACCESSIBILITY } from "@/lib/constraints";
import type { LatLng, Resource, TravelMode } from "@/lib/types";
import Modal from "./Modal";
import Icon from "./Icon";
export function safeExternal(url: string | null): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol)
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
}
export function directionsUrl(
  r: Resource,
  mode?: TravelMode | null,
  origin?: LatLng | null,
): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(r.address)}&travelmode=${mode === "walk" ? "walking" : mode === "car" || mode === "rideshare" ? "driving" : "transit"}${origin ? `&origin=${encodeURIComponent(`${origin.lat},${origin.lng}`)}` : ""}`;
}
export function eligibility(r: Resource): string {
  const e = r.eligibility;
  return [
    e.min_age !== null
      ? `Ages ${e.min_age}${e.max_age ? `–${e.max_age}` : "+"}`
      : "No stated age minimum",
    e.gender ? `${e.gender === "female" ? "Women" : "Men"} only` : null,
    e.families_ok ? "Households accepted" : "Individual adults",
    e.requires_id ? "Photo ID required" : "No photo ID required",
  ]
    .filter(Boolean)
    .join(" · ");
}
export function ResourceActions({
  resource: r,
  mode,
  compact = false,
  origin,
  directionsLabel = "Directions",
}: {
  resource: Resource;
  mode?: TravelMode | null;
  compact?: boolean;
  origin?: LatLng | null;
  directionsLabel?: string;
}) {
  const website = safeExternal(r.website_url);
  const source =
    safeExternal(r.source_url) ??
    `${API_BASE}/resources/${encodeURIComponent(r.id)}`;
  return (
    <div className="resource-actions">
      {r.phone && !r.simulated && (
        <a
          className="button button-small"
          href={`tel:${r.phone.replace(/[^\d+]/g, "")}`}
          aria-label={`Call ${r.name}`}
        >
          <Icon name="phone" size={16} />
          Call
        </a>
      )}
      <a
        className="button button-small"
        href={directionsUrl(r, mode, origin)}
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon name="pin" size={16} />
        {directionsLabel}
      </a>
      {!compact && (
        <>
          {website ? (
            <a
              className="button button-small"
              href={website}
              target="_blank"
              rel="noopener noreferrer"
            >
              Visit website
              <Icon name="external" size={14} />
            </a>
          ) : (
            <span className="unavailable-action">Website not supplied</span>
          )}
          <a
            className="button button-small"
            href={source}
            target="_blank"
            rel="noopener noreferrer"
          >
            View source
            <Icon name="external" size={14} />
          </a>
        </>
      )}
    </div>
  );
}
export default function ResourceDetails({
  resource: r,
  onClose,
  mode,
  origin,
}: {
  resource: Resource | null;
  onClose: () => void;
  mode?: TravelMode | null;
  origin?: LatLng | null;
}) {
  return (
    <Modal open={!!r} onClose={onClose} title={r?.name ?? "Resource details"}>
      {r && (
        <div className="resource-detail">
          <div className="badge-row">
            <span className="service-badge">{SERVICE_LABEL[r.service]}</span>
            <span className={`status-badge ${r.status}`}>
              {STATUS_LABEL[r.status]}
            </span>
          </div>
          <p>{r.description}</p>
          <p className="alert">
            <Icon name="info" size={18} />
            Confirm hours, availability and requirements with the provider
            before leaving.
          </p>
          <dl className="detail-grid">
            <div>
              <dt>Address</dt>
              <dd>
                {r.address}
                <small>
                  {r.lat}, {r.lng}
                </small>
              </dd>
            </div>
            <div>
              <dt>Opening hours · Baltimore time</dt>
              <dd>
                {r.hours.map((h, i) => (
                  <p key={i}>
                    {h.days.length === 7 ? "Every day" : h.days.join(", ")} ·{" "}
                    {timeLabel(h.open)}–{timeLabel(h.close)}
                    {h.close <= h.open ? " (next day)" : ""}
                  </p>
                ))}
              </dd>
            </div>
            <div>
              <dt>Last intake</dt>
              <dd>
                {r.intake_deadline
                  ? timeLabel(r.intake_deadline)
                  : "No separate intake deadline supplied"}
              </dd>
            </div>
            <div>
              <dt>Known requirements</dt>
              <dd>{eligibility(r)}</dd>
            </div>
            <div>
              <dt>Required documents</dt>
              <dd>
                {r.eligibility.required_documents.join(", ") || "None listed"}
              </dd>
            </div>
            <div>
              <dt>Service cost</dt>
              <dd>{formatUsd(r.cost)}</dd>
            </div>
            <div>
              <dt>Capacity</dt>
              <dd>
                {r.simulated || r.capacity === null
                  ? "Not confirmed"
                  : `${r.capacity} places`}
              </dd>
            </div>
            <div>
              <dt>Children / pets</dt>
              <dd>
                Children:{" "}
                {r.eligibility.children_ok === null
                  ? "Not confirmed"
                  : r.eligibility.children_ok
                    ? "Accepted"
                    : "Not accepted"}{" "}
                · Pets:{" "}
                {r.eligibility.pets_ok === null
                  ? "Not confirmed"
                  : r.eligibility.pets_ok
                    ? "Accepted"
                    : "Not accepted"}
              </dd>
            </div>
            <div>
              <dt>Accessibility</dt>
              <dd>
                {r.eligibility.accessibility
                  .map(
                    (a) => ACCESSIBILITY[a as keyof typeof ACCESSIBILITY] || a,
                  )
                  .join(", ") || "Not confirmed"}
              </dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>
                {r.simulated ? "Not confirmed" : r.phone || "Not supplied"}
              </dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{r.notes || "No additional notes"}</dd>
            </div>
            <div>
              <dt>Source and verification</dt>
              <dd>
                {r.last_verified
                  ? `Last verified ${r.last_verified}`
                  : "Not verified"}
                <small>
                  Record: {r.id}
                  {r.tags.length ? ` · ${r.tags.join(", ")}` : ""}
                </small>
              </dd>
            </div>
          </dl>
          <ResourceActions resource={r} mode={mode} origin={origin} />
        </div>
      )}
    </Modal>
  );
}
