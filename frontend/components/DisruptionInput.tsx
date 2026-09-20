"use client";
import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { Spinner } from "./ui";

export type ChangeMessage = { role: "user" | "assistant"; text: string; error?: boolean };

const QUICK = [
  "I missed the bus",
  "I'm running 20 minutes late",
  "They said they're full",
  "The bus is delayed 15 minutes",
  "I lost my ID",
];

export default function DisruptionInput({
  open,
  onOpenChange,
  onSubmit,
  busy,
  messages,
  suggestions = [],
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (text: string) => void;
  busy: boolean;
  messages: ChangeMessage[];
  suggestions?: string[];
}) {
  const [text, setText] = useState("");
  const [bubbleDismissed, setBubbleDismissed] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const log = logRef.current;
    if (open && log) log.scrollTop = log.scrollHeight;
  }, [open, messages, busy]);
  const inputRef = useRef<HTMLInputElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) inputRef.current?.focus({ preventScroll: true });
  }, [open]);
  const close = () => {
    onOpenChange(false);
    toggleRef.current?.focus({ preventScroll: true });
  };
  const send = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    onSubmit(trimmed);
    setText("");
  };
  const chips = [...suggestions, ...QUICK.filter((q) => !suggestions.includes(q))];
  return (
    <section
      className="disruption-dock"
      aria-label="Something changed"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          close();
        }
      }}
    >
      {open && <div className="disruption-dock-inner" id="disruption-panel">
        <button type="button" className="icon-button disruption-close" aria-label="Close changes panel" onClick={close}>
          <Icon name="close" size={18} />
        </button>
        <div className="disruption-head">
          <span className="eyebrow">
            <Icon name="warning" size={14} /> SOMETHING CHANGED?
          </span>
          <span className="muted small">
            Tell us what happened. The plan is checked again from where you are.
          </span>
        </div>
        <div className="disruption-log" ref={logRef} role="log" aria-label="Plan change history" aria-live="polite" aria-relevant="additions text">
          {messages.length === 0 && <p className="muted small disruption-log-empty">Changes you report and plan updates will appear here.</p>}
          {messages.map((message, index) => (
            <div key={index} className={`disruption-message disruption-message-${message.role}${message.error ? " disruption-message-error" : ""}`}>
              <span className="disruption-message-author">{message.role === "user" ? "You" : "Lighthouse"}</span>
              <p>{message.text}</p>
            </div>
          ))}
          {busy && <p className="muted small">Checking your plan…</p>}
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
            ref={inputRef}
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
      </div>}
      <div className="disruption-launcher">
        {!open && !bubbleDismissed && <span className="disruption-bubble">
          Something changed?
          <button type="button" className="disruption-bubble-close" aria-label="Dismiss Something changed hint" onClick={() => {
            setBubbleDismissed(true);
            toggleRef.current?.focus({ preventScroll: true });
          }}><Icon name="close" size={11} /></button>
        </span>}
        <button
          ref={toggleRef}
          type="button"
          className="brand-mark disruption-toggle"
          aria-label={open ? "Close changes panel" : "Something changed? Open changes panel"}
          aria-expanded={open}
          aria-controls={open ? "disruption-panel" : undefined}
          onClick={() => open ? close() : onOpenChange(true)}
        >
          <Icon name="lighthouse" size={24} />
        </button>
      </div>
    </section>
  );
}
