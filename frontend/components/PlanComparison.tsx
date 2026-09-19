import type { Plan, Strategy } from "@/lib/types";
import { formatUsd } from "@/lib/format";
import Icon from "./Icon";
export const STRATEGY_LABEL: Record<Strategy, string> = {
  recommended: "Recommended",
  fastest: "Fastest",
  lowest_cost: "Lowest cost",
};
export default function PlanComparison({
  plans,
  selected,
  onSelect,
  note,
}: {
  plans: Plan[];
  selected: string;
  onSelect: (id: string) => void;
  note: string;
}) {
  const routeCount = plans.filter((p) => p.resource_ids.length > 0).length;
  return (
    <section className="plan-comparison">
      <div className="section-kicker">
        <span className="step-number">03</span> YOUR OPTIONS
        <span className="options-count">
          {routeCount} {routeCount === 1 ? "route" : "routes"}
        </span>
      </div>
      <h2>
        {routeCount
          ? "Choose what works for you."
          : "No route fits these details yet."}
      </h2>
      {routeCount > 0 && (
        <fieldset className="strategy-options">
          <legend className="sr-only">Plan strategy</legend>
          {plans.map((p) => (
            <label
              className={`strategy-card ${selected === p.plan_id ? "active" : ""}`}
              key={p.plan_id}
            >
              <input
                type="radio"
                name="plan-strategy"
                checked={selected === p.plan_id}
                onChange={() => onSelect(p.plan_id)}
              />
              <span className="strategy-name">
                <Icon
                  name={
                    p.strategy === "recommended"
                      ? "shield"
                      : p.strategy === "fastest"
                        ? "clock"
                        : "route"
                  }
                  size={18}
                />
                {STRATEGY_LABEL[p.strategy]}
                <span className="radio-dot" />
              </span>
              <span className="strategy-numbers">
                {formatUsd(p.total_cost_usd)}
                <small> · {p.total_travel_min} min travel</small>
              </span>
              <span className="strategy-tradeoff">{p.tradeoff}</span>
              {!p.feasible && (
                <span className="partial-label">Partial plan</span>
              )}
            </label>
          ))}
        </fieldset>
      )}
      {note && (
        <p className="comparison-note">
          <Icon name="info" size={15} />
          {note}
        </p>
      )}
    </section>
  );
}
