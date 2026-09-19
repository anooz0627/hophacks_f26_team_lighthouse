import type { RejectedResource } from "@/lib/types";
import Icon from "./Icon";

export default function RejectedPanel({
  rejected,
}: {
  rejected: RejectedResource[];
}) {
  return (
    <details className="checked-options">
      <summary>
        <Icon name="shield" size={18} />
        Why other options weren’t selected<span>{rejected.length} checked</span>
        <Icon name="chevron" size={16} />
      </summary>
      {rejected.length ? (
        <ul>
          {rejected.map((r) => (
            <li key={r.resource_id}>
              <strong>{r.name}</strong>
              <span>{r.reason}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>
          No resources failed a hard check. The options above differ by travel,
          cost or timing.
        </p>
      )}
    </details>
  );
}
