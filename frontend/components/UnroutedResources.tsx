import type { Plan, Resource, TravelMode } from "@/lib/types";
import { SERVICE_LABEL, timeLabel } from "@/lib/format";
import { ResourceActions } from "./ResourceDetails";
import Icon from "./Icon";

export default function UnroutedResources({
  plan,
  resources,
  onDetails,
  onEditLocation,
  onEditDetails,
}: {
  plan: Plan;
  resources: Resource[];
  onDetails: (resource: Resource) => void;
  onEditLocation: () => void;
  onEditDetails: () => void;
}) {
  const options = (plan.unrouted_resources ?? []).flatMap((option) => {
    const resource = resources.find((r) => r.id === option.resource_id);
    return resource ? [{ ...option, resource }] : [];
  });
  if (!options.length) return null;
  const transport = plan.constraints.constraints.transport;
  const mode: TravelMode =
    transport === "walking"
      ? "walk"
      : transport === "own_vehicle"
        ? "car"
        : transport === "rideshare"
          ? "rideshare"
          : "bus";
  return (
    <section
      className="unrouted-resources"
      aria-label="Places with unconfirmed routes"
    >
      <div className="panel route-notice">
        <h3>
          <Icon name="pin" size={20} /> Route confirmation needed
        </h3>
        <p>
          These places passed the available eligibility checks. We couldn’t
          confirm a route from your starting point within your travel
          preferences and budget.
        </p>
        <p>
          Check the route, opening hours and availability before leaving. Travel
          time and fare are not included.
        </p>
        <div className="resource-actions">
          <button className="button button-small" onClick={onEditLocation}>
            Change starting location
          </button>
          <button className="button button-small" onClick={onEditDetails}>
            Review travel &amp; support
          </button>
        </div>
      </div>
      <ul>
        {options.map(({ resource, distance_km, warnings }) => (
          <li key={resource.id} className="panel contact-option">
            <span className="section-kicker">
              {SERVICE_LABEL[resource.service]}
            </span>
            <h3>{resource.name}</h3>
            <p>{resource.address}</p>
            <p className="muted small">
              {distance_km.toFixed(1)} km away in a straight line · route
              unconfirmed
            </p>
            <p className="small">
              <strong>Listed hours: </strong>
              {resource.hours.length
                ? resource.hours
                    .map(
                      (h) =>
                        `${h.days.length === 7 ? "Daily" : h.days.join(", ")} ${timeLabel(h.open)}–${timeLabel(h.close)}${h.close <= h.open ? " (next day)" : ""}`,
                    )
                    .join("; ")
                : "Not supplied"}
            </p>
            {!!warnings.length && (
              <ul className="contact-warnings">
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
            <ResourceActions
              resource={resource}
              mode={mode}
              origin={plan.constraints.constraints.current_location}
              compact
              directionsLabel="Check route in Google Maps"
            />
            <button className="text-button" onClick={() => onDetails(resource)}>
              Hours, requirements &amp; source <Icon name="arrow" size={15} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
