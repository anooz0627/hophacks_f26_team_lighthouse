"use client";
import { useState } from "react";
import Icon from "./Icon";
import { Spinner } from "./ui";

const QUICK = [
  "I missed the bus",
  "I'm running 20 minutes late",
  "They said they're full",
  "The bus is delayed 15 minutes",
  "I lost my ID",
];

export default function DisruptionInput({
  onSubmit,
  busy,
  lastMessage,
  suggestions = [],
}: {
  onSubmit: (text: string) => void;
  busy: boolean;
  lastMessage?: string;
  suggestions?: string[];
}) {
  const [text, setText] = useState("");
  const send = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    onSubmit(trimmed);
    setText("");
  };
  const chips = [...suggestions, ...QUICK.filter((q) => !suggestions.includes(q))];
  return (
    <section className="disruption-dock" aria-label="Something changed">
      <div className="disruption-dock-inner">
        <div className="disruption-head">
          <span className="eyebrow">
            <Icon name="warning" size={14} /> SOMETHING CHANGED?
          </span>
          <span className="muted small">
            Tell us what happened. The plan is checked again from where you are.
          </span>
        </div>
        <div className="chips disruption-chips" aria-label="Common changes">
          {chips.map((q, i) => (
            <button
              key={q}
              type="button"
              className={`chip ${i < suggestions.length ? "selected" : ""}`}
              disabled={busy}
              onClick={() => send(q)}
            >
              {q}
            </button>
          ))}
        </div>
        <form
          className="disruption-row"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <label htmlFor="disruption" className="sr-only">
            What changed
          </label>
          <input
            id="disruption"
            value={text}
            disabled={busy}
            maxLength={500}
            placeholder="e.g. I missed the bus and the shelter is full"
            onChange={(e) => setText(e.target.value)}
          />
          <button
            type="submit"
            className="button button-primary"
            disabled={busy || !text.trim()}
          >
            {busy ? <Spinner /> : <Icon name="route" size={16} />}
            Update plan
          </button>
        </form>
        {lastMessage && (
          <p className="disruption-result" role="status">
            {lastMessage}
          </p>
        )}
      </div>
    </section>
  );
}
