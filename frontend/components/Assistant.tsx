"use client";
import { useState, type ReactNode } from "react";
import GuideVisual from "./GuideVisual";
export type AssistantState =
  | "idle"
  | "listening"
  | "understanding"
  | "building"
  | "ready"
  | "warning"
  | "replanning"
  | "completed"
  | "no-plan";
const labels: Record<AssistantState, string> = {
  idle: "Here to help",
  listening: "Listening",
  understanding: "Understanding your situation",
  building: "Checking your options",
  ready: "Your next steps are ready",
  warning: "A detail needs your attention",
  replanning: "Finding another way",
  completed: "One step at a time",
  "no-plan": "Let’s look at your options",
};
const messages: Record<AssistantState, string> = {
  idle: "Tell me what you need today. We’ll work through the next steps together.",
  listening:
    "Use your own words. You can add or change details before we plan.",
  understanding: "I’m picking out your needs, timing and travel options.",
  building:
    "I’m checking eligibility, opening hours and the cost of getting there.",
  ready:
    "Start with the first action. Check the requirements and call ahead before traveling.",
  warning: "Review the highlighted details so the plan fits your situation.",
  replanning:
    "Availability changed. I’m checking a replacement against your details.",
  completed: "That step is done. Your next action is ready when you are.",
  "no-plan":
    "Some needs don’t have a matching route. Review the reasons or contact 211 for more options.",
};
export default function Assistant({
  state,
  message,
  visual,
  reviewing = false,
}: {
  state: AssistantState;
  message?: string;
  visual?: ReactNode;
  reviewing?: boolean;
}) {
  const [hideCharacter, setHideCharacter] = useState(false);
  const [still, setStill] = useState(false);
  return (
    <aside
      className={`assistant assistant-companion assistant-${state}`}
      aria-label="Planning assistant"
    >
      {!hideCharacter && (
        <div className="assistant-visual" aria-hidden="true">
          {visual ?? (
            <GuideVisual state={state} still={still} reviewing={reviewing} />
          )}
        </div>
      )}
      <div className="assistant-copy">
        <div aria-live="polite" aria-atomic="true">
          <span className="eyebrow">YOUR GUIDE</span>
          <h3>{labels[state]}</h3>
          <p>{message || messages[state]}</p>
        </div>
        <div className="assistant-options">
          <button
            type="button"
            onClick={() => setHideCharacter(!hideCharacter)}
            aria-pressed={hideCharacter}
          >
            {hideCharacter ? "Show character" : "Hide character"}
          </button>
          {!hideCharacter && !visual && (
            <button
              type="button"
              onClick={() => setStill(!still)}
              aria-pressed={still}
            >
              {still ? "Allow motion" : "Pause motion"}
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
