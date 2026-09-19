import type { PlanDiff, Resource } from "@/lib/types";
import Icon from "./Icon";
export default function ReplanBanner({
  diff,
  resources,
  onDismiss,
}: {
  diff: PlanDiff;
  resources: Resource[];
  onDismiss: () => void;
}) {
  const name = (id: string) => resources.find((r) => r.id === id)?.name ?? id;
  return (
    <div className="replan-banner" role="status">
      <Icon name={diff.feasible ? "route" : "warning"} />
      <div>
        <strong>
          {diff.feasible
            ? "We found another way."
            : "Your plan needs attention."}
        </strong>
        <p>{diff.trigger}.</p>
        {diff.removed_resource_ids.length > 0 && (
          <div className="replacement-pair">
            <span>
              <small>PREVIOUS</small>
              {diff.removed_resource_ids.map(name).join(" · ")}
            </span>
            <Icon name="arrow" />
            <span>
              <small>REPLACEMENT</small>
              {diff.added_resource_ids.length
                ? diff.added_resource_ids.map(name).join(" · ")
                : "No matching replacement found"}
            </span>
          </div>
        )}
        <p>
          {diff.travel_delta_min === 0
            ? "Travel time is unchanged."
            : `The updated route takes ${Math.abs(diff.travel_delta_min)} ${diff.travel_delta_min > 0 ? "more" : "fewer"} travel minutes.`}
          {diff.cost_delta_usd !== 0 &&
            ` Estimated cost ${diff.cost_delta_usd > 0 ? "increases" : "decreases"} by $${Math.abs(diff.cost_delta_usd).toFixed(2)}.`}{" "}
          {diff.feasible
            ? "The new arrival times fit the listed intake windows."
            : "Review the missing needs below."}
        </p>
      </div>
      <button
        className="icon-button"
        onClick={onDismiss}
        aria-label="Dismiss plan update"
      >
        <Icon name="close" size={17} />
      </button>
    </div>
  );
}
