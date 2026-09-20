import type { BlockedNeed, Resource } from "@/lib/types";
import { SERVICE_LABEL } from "@/lib/format";
import Icon from "./Icon";

export default function BlockedNeeds({
  blocked,
  resources,
  onDetails,
  onStuck,
}: {
  blocked: BlockedNeed[];
  resources: Resource[];
  onDetails: (resource: Resource) => void;
  onStuck: () => void;
}) {
  if (!blocked.length) return null;
  return (
    <section className="panel blocked-needs" aria-label="What is blocking the plan">
      <div className="section-kicker">
        <Icon name="warning" size={16} /> WHAT IS BLOCKING THIS
      </div>
      <ul>
        {blocked.map((b) => {
          const helper = resources.find((r) => r.id === b.first_step_resource_id);
          return (
            <li key={b.need}>
              <strong>{SERVICE_LABEL[b.need]}</strong>
              <p>{b.summary}</p>
              <p className="blocked-next">
                <Icon name="arrow" size={14} /> {b.suggestion}
              </p>
              {helper && (
                <button className="text-button" onClick={() => onDetails(helper)}>
                  First step: {helper.name}
                  <Icon name="arrow" size={14} />
                </button>
              )}
              <small className="muted">
                {b.checked} option{b.checked === 1 ? "" : "s"} checked
              </small>
            </li>
          );
        })}
      </ul>
      <button className="button button-small" onClick={onStuck}>
        Tell us what changed
      </button>
    </section>
  );
}
