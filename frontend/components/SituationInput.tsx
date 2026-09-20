"use client";
import type { Constraints, Deadline, Need, UserConstraints } from "@/lib/types";
import ConstraintFields from "./ConstraintFields";
import SpeechInput from "./SpeechInput";
import Icon from "./Icon";
import { Spinner } from "./ui";
export type Phase =
  | "idle"
  | "extracting"
  | "review"
  | "planning"
  | "planned"
  | "replanning";
export const EXAMPLES = [
  "I'm 19. I lost my housing today, don't have a car, have $10, and need somewhere to sleep tonight.",
  "Me and my two kids got evicted this morning. I have my ID and $25 but no car. We need dinner and somewhere to stay tonight.",
  "I'm 22, in Mount Vernon. I need food tonight, have no money, and can only walk.",
];
const SCENARIOS = [
  { label: "A place for tonight", icon: "home" },
  { label: "Help for my family", icon: "support" },
  { label: "A meal nearby", icon: "food" },
] as const;
export default function SituationInput({
  text,
  onTextChange,
  onSubmit,
  phase,
  error,
  details,
  onPatch,
  onNeeds,
  onDeadline,
  deadlineValue,
  voiceAvailable,
  voiceBusy,
  onVoiceBusy,
  onTranscript,
}: {
  text: string;
  onTextChange: (text: string, example?: boolean) => void;
  onSubmit: () => void;
  phase: Phase;
  error: string | null;
  details: UserConstraints;
  onPatch: (patch: Partial<Constraints>) => void;
  onNeeds: (needs: Need[]) => void;
  onDeadline: (deadline: Deadline) => void;
  deadlineValue?: Deadline;
  voiceAvailable: boolean;
  voiceBusy: boolean;
  onVoiceBusy: (busy: boolean) => void;
  onTranscript: (text: string) => void;
}) {
  const busy =
    voiceBusy || ["extracting", "planning", "replanning"].includes(phase);
  return (
    <section className="panel situation-panel">
      <div className="section-kicker">
        <span className="step-number">01</span> YOUR SITUATION
      </div>
      <h2 id="situation-heading" tabIndex={-1}>
        What do you need help with today?
      </h2>
      <p className="muted">Start wherever you are. A few words are enough.</p>
      <form
        onInvalidCapture={(event) => {
          const section = (event.target as HTMLElement).closest("details");
          if (section) section.open = true;
        }}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <SpeechInput
          disabled={["extracting", "planning", "replanning"].includes(phase)}
          available={voiceAvailable}
          onBusyChange={onVoiceBusy}
          onTranscript={onTranscript}
        />
        <label htmlFor="situation" className="sr-only">
          Describe your situation
        </label>
        <textarea
          id="situation"
          rows={6}
          maxLength={10000}
          required
          disabled={busy}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder="For example, I’m 19, I need somewhere to sleep tonight, I don’t have a car, and I have $10…"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter")
              e.currentTarget.form?.requestSubmit();
          }}
        />
        {error && (
          <p className="alert error" role="alert">
            {error}
          </p>
        )}
        <button
          className="button button-primary full-width"
          disabled={busy || !text.trim()}
          type="submit"
        >
          {voiceBusy ? (
            "Finish voice input to continue"
          ) : busy ? (
            <>
              <Spinner />
              {phase === "extracting"
                ? "Understanding…"
                : "Checking your plan…"}
            </>
          ) : (
            <>
              Review my details
              <Icon name="arrow" />
            </>
          )}
        </button>
        <p className="example-label">Or start with an example</p>
        <div className="scenario-buttons">
          {SCENARIOS.map(({ label, icon }, i) => (
            <button
              key={label}
              type="button"
              className="scenario"
              disabled={busy}
              onClick={() => onTextChange(EXAMPLES[i], true)}
            >
              <Icon name={icon} size={16} />
              {label}
              <span aria-hidden>↗</span>
            </button>
          ))}
        </div>
        <details className="customize">
          <summary>
            <Icon name="settings" size={17} />
            Add details<span className="optional">optional</span>
            <Icon name="chevron" size={16} />
          </summary>
          <ConstraintFields
            value={details}
            onPatch={onPatch}
            onNeeds={onNeeds}
            disabled={busy}
            onDeadline={onDeadline}
            deadlineValue={deadlineValue}
          />
        </details>
        <p className="privacy-note">
          <Icon name="shield" size={15} />
          No account needed. You’re in control of the details.
        </p>
      </form>
    </section>
  );
}
