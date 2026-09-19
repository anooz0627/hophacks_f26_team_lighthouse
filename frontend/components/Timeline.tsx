"use client";

import type { Plan, PlanStep, Resource } from "@/lib/types";
import {
  SERVICE_LABEL,
  STATUS_LABEL,
  formatUsd,
  timeLabel,
} from "@/lib/format";
import Icon from "./Icon";
import { ResourceActions, eligibility } from "./ResourceDetails";

export const stepKey = (step: PlanStep) =>
  `${step.type}:${step.resource_id}:${step.time_iso}:${step.mode ?? ""}:${step.duration_min ?? 0}:${step.cost_usd}`;

export default function Timeline({
  plan,
  resources,
  updating,
  highlightIds,
  completed,
  onComplete,
  onDetails,
}: {
  plan: Plan;
  resources: Resource[];
  updating: boolean;
  highlightIds: string[];
  completed: Set<string>;
  onComplete: (step: PlanStep) => void;
  onDetails: (resource: Resource) => void;
}) {
  const dates = [
    ...new Set(
      plan.steps
        .filter((s) => s.type !== "note")
        .map((s) => s.time_iso.slice(0, 10)),
    ),
  ];
  const tomorrow = new Date(`${plan.now.slice(0, 10)}T12:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  const tomorrowDate = tomorrow.toISOString().slice(0, 10);

  return (
    <section
      className="timeline"
      aria-label="Your actionable timeline"
      aria-busy={updating}
    >
      {plan.unmet_needs.length > 0 && (
        <div className="alert warning" role="status">
          <Icon name="warning" />
          <div>
            <strong>
              {plan.resource_ids.length
                ? "This plan covers some of your needs"
                : "No feasible plan found"}
            </strong>
            <p>
              Still needed:{" "}
              {plan.unmet_needs.map((n) => SERVICE_LABEL[n]).join(", ")}. Review
              the checked options, adjust your details, or{" "}
              <a href="tel:211">call 211</a>.
            </p>
          </div>
        </div>
      )}
      {dates.map((date, index) => (
        <div className="timeline-day" key={date}>
          <div className="day-heading">
            <h3>
              {date === plan.now.slice(0, 10)
                ? "Tonight"
                : date === tomorrowDate
                  ? "Tomorrow"
                  : new Date(`${date}T12:00:00`).toLocaleDateString("en-US", {
                      weekday: "long",
                      month: "short",
                      day: "numeric",
                    })}
            </h3>
            <span>
              {index === 0 ? "Your next steps" : "Keep moving forward"} ·
              estimated times
            </span>
          </div>
          <ol>
            {plan.steps
              .filter((s) => s.type !== "note" && s.time_iso.startsWith(date))
              .map((step) => {
                const r = resources.find((r) => r.id === step.resource_id);
                const done = completed.has(stepKey(step));
                const isVisit = step.type === "visit";
                const travel = plan.steps.find(
                  (s) =>
                    s.type === "travel" && s.resource_id === step.resource_id,
                );
                return (
                  <li
                    key={step.order}
                    className={`timeline-row ${isVisit ? "visit-row" : "compact-row"} ${done ? "step-done" : ""}`}
                  >
                    <div className="time-label">
                      {timeLabel(step.time)}
                      <span>est.</span>
                    </div>
                    <div
                      className={`timeline-node ${isVisit ? r?.service : step.type}`}
                    >
                      <Icon
                        name={
                          done
                            ? "check"
                            : step.type === "call"
                              ? "phone"
                              : step.type === "travel"
                                ? "route"
                                : r?.service === "food"
                                  ? "food"
                                  : r?.service === "emergency_housing"
                                    ? "home"
                                    : "support"
                        }
                        size={18}
                      />
                    </div>
                    <article
                      className={`step-card ${highlightIds.includes(step.resource_id ?? "") ? "replacement" : ""}`}
                    >
                      <div className="step-topline">
                        {isVisit && r && (
                          <span className="step-service">
                            {SERVICE_LABEL[r.service]}
                          </span>
                        )}
                        {highlightIds.includes(step.resource_id ?? "") && (
                          <span className="replacement-label">Replacement</span>
                        )}
                        {isVisit && r && (
                          <span className={`status-badge ${r.status}`}>
                            {STATUS_LABEL[r.status]}
                          </span>
                        )}
                      </div>
                      <h4>{step.title}</h4>
                      {isVisit && r ? (
                        <>
                          <p className="step-address">
                            <Icon name="pin" size={15} />
                            {r.address}
                          </p>
                          <div className="step-facts">
                            <span>
                              <Icon name="clock" size={15} />
                              {travel?.duration_min ?? 0} min travel
                            </span>
                            <span>
                              {formatUsd(
                                step.cost_usd + (travel?.cost_usd ?? 0),
                              )}{" "}
                              incl. travel
                            </span>
                            {r.intake_deadline && (
                              <span>
                                Intake by {timeLabel(r.intake_deadline)}
                              </span>
                            )}
                          </div>
                          <p className="service-hours">
                            {step.detail.replace(/\b(\d{2}:\d{2})\b/g, (time) =>
                              timeLabel(time),
                            )}
                          </p>
                          <p className="requirements">
                            <strong>Requirements</strong>
                            {eligibility(r)}
                          </p>
                          <p className="requirements">
                            <strong>Bring</strong>
                            {step.bring.join(", ") || "No documents listed"}
                          </p>
                          <p className="why-selected">
                            <Icon name="check" size={15} />
                            Selected for your{" "}
                            {r.eligibility.requires_id
                              ? "budget and arrival window"
                              : "budget, arrival window and no-ID access"}
                            .
                          </p>
                          {step.warnings.length > 0 && (
                            <div className="step-warnings">
                              {step.warnings.map((w) => (
                                <p key={w}>
                                  <Icon name="warning" size={15} />
                                  {w}
                                </p>
                              ))}
                            </div>
                          )}
                          <ResourceActions resource={r} mode={travel?.mode} />
                          <div className="step-footer">
                            <button
                              className="text-button"
                              onClick={() => onDetails(r)}
                            >
                              View resource details
                              <Icon name="arrow" size={15} />
                            </button>
                            <button
                              className={`complete-button ${done ? "is-complete" : ""}`}
                              aria-pressed={done}
                              onClick={() => onComplete(step)}
                            >
                              <span className="complete-box">
                                {done && <Icon name="check" size={13} />}
                              </span>
                              {done ? "Completed" : "Mark step complete"}
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p className="muted small">
                            {step.type === "call" && r?.simulated
                              ? "Contact the provider to confirm a place, intake time and required documents."
                              : step.detail}
                          </p>
                          {r && step.type === "call" && (
                            <p className="small">
                              {r.eligibility.requires_id
                                ? "Photo ID required at intake."
                                : "No photo ID required."}{" "}
                              Confirm availability before leaving.
                            </p>
                          )}
                          <div className="compact-actions">
                            {r && (
                              <ResourceActions
                                resource={r}
                                mode={step.mode ?? travel?.mode}
                                compact
                              />
                            )}
                            <button
                              className={`complete-button ${done ? "is-complete" : ""}`}
                              aria-pressed={done}
                              onClick={() => onComplete(step)}
                            >
                              <span className="complete-box">
                                {done && <Icon name="check" size={13} />}
                              </span>
                              {done ? "Completed" : "Mark step complete"}
                            </button>
                          </div>
                        </>
                      )}
                    </article>
                  </li>
                );
              })}
          </ol>
        </div>
      ))}
    </section>
  );
}
