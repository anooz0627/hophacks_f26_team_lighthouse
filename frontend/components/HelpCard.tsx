"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Plan, PlanStep, Resource } from "@/lib/types";
import { SERVICE_LABEL, timeLabel } from "@/lib/format";
import { speakText } from "@/lib/api";
import Icon from "./Icon";
import Modal from "./Modal";
import { Spinner } from "./ui";

type Line = { id: string; text: string; on: boolean };

function buildLines(
  plan: Plan,
  step: PlanStep | null,
  resource?: Resource,
): Line[] {
  const c = plan.constraints.constraints;
  const needs = plan.constraints.needs
    .map((n) => SERVICE_LABEL[n.type].toLowerCase())
    .join(", ");
  const lines: Line[] = [
    { id: "needs", text: `I am looking for ${needs} today.`, on: true },
  ];
  if (step && resource) {
    const intake =
      step.type === "visit" && resource.intake_deadline
        ? ` Intake closes at ${timeLabel(resource.intake_deadline)}.`
        : "";
    lines.push({
      id: "next",
      text: `My next step is ${resource.name}.${intake}`,
      on: true,
    });
  }
  if (c.has_id === false)
    lines.push({ id: "id", text: "I do not have a photo ID.", on: true });
  if (c.has_id === true)
    lines.push({ id: "id", text: "I have my photo ID with me.", on: false });
  if (c.budget_usd !== null && c.budget_usd !== undefined)
    lines.push({
      id: "budget",
      text: `I have $${c.budget_usd} for travel and fees.`,
      on: true,
    });
  if (c.family_size > 1)
    lines.push({
      id: "family",
      text: `There are ${c.family_size} of us together${c.children ? ", including children" : ""}.`,
      on: true,
    });
  if (c.transport === "walking" || c.transport === "no_vehicle")
    lines.push({
      id: "transport",
      text: "I do not have a car. I am walking or taking the bus.",
      on: true,
    });
  lines.push({
    id: "calls",
    text: "Phone calls are hard for me. Please write things down.",
    on: false,
  });
  lines.push({
    id: "desk",
    text: "Please point me to the intake desk or the person who can help.",
    on: true,
  });
  return lines;
}

export default function HelpCard({
  open,
  onClose,
  plan,
  step,
  resource,
  voice,
}: {
  open: boolean;
  onClose: () => void;
  plan: Plan;
  step: PlanStep | null;
  resource?: Resource;
  voice: boolean;
}) {
  const base = useMemo(
    () => buildLines(plan, step, resource),
    [plan, step, resource],
  );
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const lines = base.map((l) => ({ ...l, on: overrides[l.id] ?? l.on }));
  const [custom, setCustom] = useState("");
  const [audio, setAudio] = useState<"idle" | "loading" | "playing" | "error">(
    "idle",
  );
  const player = useRef<HTMLAudioElement | null>(null);
  useEffect(
    () => () => {
      player.current?.pause();
    },
    [],
  );
  useEffect(() => {
    if (!open) return;
    document.body.classList.add("help-card-open");
    return () => document.body.classList.remove("help-card-open");
  }, [open]);
  const shown = [
    ...lines.filter((l) => l.on).map((l) => l.text),
    ...(custom.trim() ? [custom.trim()] : []),
  ];
  const speak = async () => {
    if (audio === "playing") {
      player.current?.pause();
      setAudio("idle");
      return;
    }
    setAudio("loading");
    try {
      const url = await speakText(shown.join(" "));
      const el = new Audio(url);
      el.onended = () => setAudio("idle");
      el.onerror = () => setAudio("error");
      player.current = el;
      await el.play();
      setAudio("playing");
    } catch {
      setAudio("error");
    }
  };
  const printable =
    open && typeof document !== "undefined"
      ? createPortal(
          <div className="help-print" aria-hidden="true">
            <p className="help-print-title">Lighthouse help card</p>
            {shown.map((t) => (
              <p key={t}>{t}</p>
            ))}
          </div>,
          document.body,
        )
      : null;
  return (
    <>
      {printable}
      <Modal open={open} onClose={onClose} title="Help card" wide>
        <p className="muted">
          Show this screen to a staff member. Tick what you want to share.
        </p>
        <div className="help-card" role="region" aria-label="Help card text">
          {shown.length ? (
            shown.map((t) => <p key={t}>{t}</p>)
          ) : (
            <p className="muted">Select at least one line below.</p>
          )}
        </div>
        <div className="help-actions">
          {voice && (
            <button
              className="button"
              onClick={() => void speak()}
              disabled={audio === "loading" || !shown.length}
            >
              {audio === "loading" ? (
                <Spinner />
              ) : (
                <Icon name="speaker" size={16} />
              )}
              {audio === "playing" ? "Stop" : "Read aloud"}
            </button>
          )}
          <button className="button" onClick={() => window.print()}>
            <Icon name="external" size={16} /> Print or save
          </button>
          {audio === "error" && (
            <span className="muted small">Audio is unavailable right now.</span>
          )}
        </div>
        <div className="help-lines">
          {lines.map((l) => (
            <label key={l.id} className="check-field">
              <input
                type="checkbox"
                checked={l.on}
                onChange={(e) =>
                  setOverrides((old) => ({ ...old, [l.id]: e.target.checked }))
                }
              />
              {l.text}
            </label>
          ))}
          <label className="field">
            <span className="field-label">Add your own line</span>
            <input
              value={custom}
              maxLength={160}
              onChange={(e) => setCustom(e.target.value)}
              placeholder="e.g. I need a place that accepts my dog."
            />
          </label>
        </div>
      </Modal>
    </>
  );
}
