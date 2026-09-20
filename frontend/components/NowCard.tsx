"use client";
import type { PlanStep, Resource } from "@/lib/types";
import { timeLabel } from "@/lib/format";
import Icon from "./Icon";

export default function NowCard({
  step,
  resource,
  done,
  total,
  onDone,
  onStuck,
  onShowCard,
}: {
  step: PlanStep | null;
  resource?: Resource;
  done: number;
  total: number;
  onDone: () => void;
  onStuck: () => void;
  onShowCard: () => void;
}) {
  if (!step && total === 0) return null;
  if (!step) {
    return (
      <section className="panel now-card now-complete" aria-label="Right now">
        <div className="section-kicker">
          <Icon name="check" size={16} /> ALL STEPS DONE
        </div>
        <h2>You’ve finished every step in this plan.</h2>
        <p className="muted">
          Keep the help card handy in case you need to explain your situation
          again.
        </p>
        <div className="now-actions">
          <button className="button" onClick={onShowCard}>
            <Icon name="info" size={16} /> Show help card
          </button>
        </div>
      </section>
    );
  }
  const facts: string[] = [];
  if (resource?.address) facts.push(resource.address);
  if (step.type === "visit" && resource?.intake_deadline)
    facts.push(`Intake by ${timeLabel(resource.intake_deadline)}`);
  if (step.duration_min && step.type === "travel")
    facts.push(`About ${step.duration_min} min`);
  if (step.bring.length) facts.push(`Bring: ${step.bring.join(", ")}`);
  return (
    <section className="panel now-card" aria-label="Right now">
      <div className="section-kicker">
        <Icon name="clock" size={16} /> RIGHT NOW
        <span className="options-count">
          Step {done + 1} of {total}
        </span>
      </div>
      <p className="now-time">
        {timeLabel(step.time)} <small>est.</small>
      </p>
      <h2>{step.title}</h2>
      {facts.length > 0 && (
        <ul className="now-facts">
          {facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      {step.type === "call" && resource?.phone && (
        <a className="now-phone" href={`tel:${resource.phone}`}>
          <Icon name="phone" size={18} /> {resource.phone}
        </a>
      )}
      <div className="now-actions">
        <button className="button button-primary now-done" onClick={onDone}>
          <Icon name="check" size={18} /> Done, next step
        </button>
        <button className="button" onClick={onStuck}>
          <Icon name="warning" size={16} /> I’m stuck
        </button>
        <button className="button button-quiet" onClick={onShowCard}>
          <Icon name="info" size={16} /> Show help card
        </button>
      </div>
    </section>
  );
}
