"use client";

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
  const routes = plans.filter((plan) => plan.resource_ids.length > 0);
  const routeCount = routes.length;
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
          {routes.map((plan) => (
            <label
              className={`strategy-card ${selected === plan.plan_id ? "active" : ""}`}
              key={plan.plan_id}
            >
              <input
                type="radio"
                name="plan-strategy"
                value={plan.plan_id}
                checked={selected === plan.plan_id}
                onChange={() => onSelect(plan.plan_id)}
              />
              <span className="strategy-name">
                <Icon
                  name={
                    plan.strategy === "recommended"
                      ? "shield"
                      : plan.strategy === "fastest"
                        ? "clock"
                        : "route"
                  }
                  size={18}
                />
                {STRATEGY_LABEL[plan.strategy]}
                <span className="radio-dot" />
              </span>
              <span className="strategy-numbers">
                {formatUsd(plan.total_cost_usd)}
                <small> · {plan.total_travel_min} min travel</small>
              </span>
              <span className="strategy-tradeoff">{plan.tradeoff}</span>
              {!plan.feasible && (
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
