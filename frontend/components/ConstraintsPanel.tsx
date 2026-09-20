import { ACCESSIBILITY, GENDERS, TRANSPORT } from "@/lib/constraints";
import { DEADLINE_LABEL, SERVICE_LABEL } from "@/lib/format";
import type { UserConstraints } from "@/lib/types";
import Icon from "./Icon";
export default function ConstraintsPanel({
  constraints,
  onEdit,
  onEditLocation,
  reviewing = false,
}: {
  constraints: UserConstraints;
  onEdit: () => void;
  onEditLocation: () => void;
  reviewing?: boolean;
}) {
  const c = constraints.constraints;
  const rows = [
    ["Budget", c.budget_usd === null ? "Not specified" : `$${c.budget_usd}`],
    ["Age", c.age === null ? "Not specified" : `${c.age} years old`],
    [
      "Photo ID",
      c.has_id === null
        ? "Unsure · confirm"
        : c.has_id
          ? "Available"
          : "Unavailable",
    ],
    ["Getting there", TRANSPORT[c.transport]],
    [
      "Starting from",
      c.current_location ? c.location_label : "Location access needed",
    ],
    [
      "Gender",
      c.gender === "self_describe"
        ? c.gender_description || "Self-described"
        : c.gender
          ? GENDERS[c.gender]
          : "Not specified",
    ],
    [
      "Household",
      `${c.family_size} ${c.family_size === 1 ? "person" : "people"}${c.children ? " · children" : ""}${c.pets ? " · pets" : ""}`,
    ],
    [
      "Support for your trip",
      c.accessibility.map((a) => ACCESSIBILITY[a]).join(", ") ||
        "None specified",
    ],
  ];
  return (
    <section
      className={`panel constraints-panel ${reviewing ? "reviewing" : ""}`}
    >
      <div className="section-kicker">
        <span className="step-number">02</span> YOUR DETAILS
        <button className="text-button" onClick={onEdit}>
          <Icon name="edit" size={15} />
          Edit
        </button>
      </div>
      <h2>
        {reviewing
          ? "Did we get this right?"
          : "What your plan is built around"}
      </h2>
      <p className="muted small">
        {reviewing
          ? "Change anything that doesn’t fit. Food and longer-term help are suggested after housing loss."
          : "Change a detail to find a plan that fits better."}
      </p>
      <div className="need-summary">
        {constraints.needs.map((n) => (
          <button key={n.type} onClick={onEdit} className="need-summary-row">
            <span className={`service-dot ${n.type}`} />
            <strong>{SERVICE_LABEL[n.type]}</strong>
            <span>
              {n.priority === "high"
                ? "High priority"
                : n.priority === "medium"
                  ? "Medium priority"
                  : "Follow-up"}
              <small>
                {n.deadline === "custom"
                  ? c.custom_deadline?.replace("T", " ") || "Add a deadline"
                  : DEADLINE_LABEL[n.deadline]}
              </small>
            </span>
            <Icon name="edit" size={14} />
          </button>
        ))}
      </div>
      <dl className="summary-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>
              <button
                onClick={label === "Starting from" ? onEditLocation : onEdit}
                aria-label={`Edit ${label}: ${value}`}
              >
                {value}
                <Icon name="edit" size={13} />
              </button>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
