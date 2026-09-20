"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import AdminDrawer from "@/components/AdminDrawer";
import Assistant, { type AssistantState } from "@/components/Assistant";
import ConstraintFields from "@/components/ConstraintFields";
import ConstraintsPanel from "@/components/ConstraintsPanel";
import Header from "@/components/Header";
import Icon from "@/components/Icon";
import Modal from "@/components/Modal";
import PlanComparison from "@/components/PlanComparison";
import RejectedPanel from "@/components/RejectedPanel";
import ReplanBanner from "@/components/ReplanBanner";
import ResourceDetails from "@/components/ResourceDetails";
import SituationInput, { type Phase } from "@/components/SituationInput";
import Timeline, { stepKey } from "@/components/Timeline";
import { Spinner } from "@/components/ui";
import {
  extract,
  generatePlans,
  getResources,
  setResourceStatus,
  resetResources,
  errorMessage,
} from "@/lib/api";
import { DEFAULT_CONSTRAINTS, emptyConstraints } from "@/lib/constraints";
import {
  demoNowIso,
  formatUsd,
  SERVICE_LABEL,
  DEADLINE_LABEL,
} from "@/lib/format";
import type {
  Constraints,
  Deadline,
  Need,
  Plan,
  PlanBundle,
  PlanStep,
  Resource,
  ResourceStatus,
  UserConstraints,
} from "@/lib/types";
const PlanMap = dynamic(() => import("@/components/PlanMap"), {
  ssr: false,
  loading: () => <p className="muted">Loading map…</p>,
});
const DEMO_NOW = demoNowIso();

export default function Home() {
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Partial<Constraints>>({});
  const [deadlineOverride, setDeadlineOverride] = useState<
    Deadline | undefined
  >();
  const [needOverrides, setNeedOverrides] = useState<Need[] | null>(null);
  const [constraints, setConstraints] = useState<UserConstraints | null>(null);
  const [bundle, setBundle] = useState<PlanBundle | null>(null);
  const [selected, setSelected] = useState("");
  const [resources, setResources] = useState<Resource[]>([]);
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [edit, setEdit] = useState<UserConstraints | null>(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [adminBusyId, setAdminBusyId] = useState<string | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [assistant, setAssistant] = useState<AssistantState>("idle");
  const [guideMessage, setGuideMessage] = useState<string | undefined>();
  const [invalidated, setInvalidated] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const planColumn = useRef<HTMLDivElement>(null);
  const [showMap, setShowMap] = useState(true);
  const operation = useRef(false);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const plan =
    bundle?.plans.find((p) => p.plan_id === selected) ??
    bundle?.plans[0] ??
    null;
  const busy = ["extracting", "planning", "replanning"].includes(phase);
  const details = {
    ...emptyConstraints(),
    constraints: { ...DEFAULT_CONSTRAINTS, ...overrides },
    needs: needOverrides ?? [],
  };

  useEffect(() => {
    let cancelled = false;
    getResources()
      .then((list) => {
        if (!cancelled) setResources(list);
      })
      .catch((err) => {
        if (!cancelled) setResourceError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    if (phase === "review" || phase === "planned") {
      reviewHeading.current?.focus({ preventScroll: true });
      if (window.matchMedia("(max-width: 780px)").matches)
        planColumn.current?.scrollIntoView({ block: "start" });
    }
  }, [phase]);

  const setSituation = (value: string, example = false) => {
    setText(value);
    setPhase("idle");
    setBundle(null);
    setConstraints(null);
    setCompleted(new Set());
    setError(null);
    setInvalidated(false);
    setAssistant(value ? "listening" : "idle");
    setGuideMessage(undefined);
    if (example) {
      setOverrides({});
      setNeedOverrides(null);
      setDeadlineOverride(undefined);
    }
  };
  const understand = async () => {
    if (operation.current || !text.trim()) return;
    operation.current = true;
    setPhase("extracting");
    setAssistant("understanding");
    setGuideMessage(undefined);
    setError(null);
    try {
      const [uc, list] = await Promise.all([
        extract(text.trim()),
        getResources(),
      ]);
      setResources(list);
      setResourceError(null);
      const reviewed = {
        ...uc,
        constraints: { ...uc.constraints, ...overrides },
        needs: (needOverrides ?? uc.needs).map((n) =>
          deadlineOverride &&
          (n.type !== "long_term_assistance" ||
            (needOverrides ?? uc.needs).length === 1)
            ? { ...n, deadline: deadlineOverride }
            : n,
        ),
      };
      setConstraints(reviewed);
      setContextOpen(false);
      setBundle(null);
      setCompleted(new Set());
      setPhase("review");
      setAssistant("warning");
      const missing = [
        reviewed.constraints.age === null ? "age" : null,
        reviewed.constraints.budget_usd === null ? "budget" : null,
        reviewed.constraints.has_id === null ? "photo ID" : null,
      ].filter(Boolean);
      setGuideMessage(
        missing.length
          ? `Please check ${missing.join(", ")}. Unknown details may leave eligibility or cost uncertain.`
          : "Check your needs and details. When they look right, I’ll find your options.",
      );
    } catch (err) {
      setError(errorMessage(err));
      setPhase("idle");
      setAssistant("warning");
    } finally {
      operation.current = false;
    }
  };
  const acceptBundle = (next: PlanBundle, previous?: Plan) => {
    const active =
      next.plans.find((p) => p.strategy === previous?.strategy) ??
      next.plans[0];
    setBundle(next);
    setSelected(active.plan_id);
    setConstraints(active.constraints);
    setInvalidated(false);
    setPhase("planned");
    setCompleted((old) =>
      previous
        ? new Set(active.steps.map(stepKey).filter((key) => old.has(key)))
        : new Set(),
    );
    setAssistant(active.feasible ? "ready" : "no-plan");
    setGuideMessage(undefined);
  };
  const build = async (uc: UserConstraints, previous?: Plan) => {
    if (operation.current) return;
    operation.current = true;
    setError(null);
    setPhase(previous ? "replanning" : "planning");
    setAssistant(previous ? "replanning" : "building");
    setGuideMessage(undefined);
    try {
      const [next, list] = await Promise.all([
        generatePlans(uc, DEMO_NOW, previous?.plan_id),
        getResources(),
      ]);
      setResources(list);
      setResourceError(null);
      acceptBundle(next, previous);
    } catch (err) {
      setError(errorMessage(err));
      setPhase(previous ? "planned" : "review");
      setAssistant("warning");
    } finally {
      operation.current = false;
    }
  };
  const updateAvailability = async (id?: string, status?: ResourceStatus) => {
    if (operation.current) return;
    operation.current = true;
    setAdminBusyId(id ?? "reset");
    setResourceError(null);
    setError(null);
    const current = plan;
    const changesActive =
      !!current && (!id || current.resource_ids.includes(id));
    if (current) {
      setPhase("replanning");
      setAssistant("replanning");
      setGuideMessage(undefined);
    }
    if (changesActive) {
      setInvalidated(true);
      setPhase("replanning");
    }
    try {
      if (id && status) {
        const updated = await setResourceStatus(id, status);
        setResources((list) => list.map((r) => (r.id === id ? updated : r)));
      } else setResources(await resetResources());
      if (current) {
        const next = await generatePlans(
          current.constraints,
          current.now,
          current.plan_id,
        );
        acceptBundle(next, current);
        if (changesActive) setAdminOpen(false);
      }
    } catch (err) {
      setResourceError(errorMessage(err));
      setError(
        changesActive
          ? "Availability could not be confirmed. Retry planning before using this route."
          : errorMessage(err),
      );
      setPhase(current ? "planned" : constraints ? "review" : "idle");
      setAssistant("warning");
      setGuideMessage(undefined);
    } finally {
      setAdminBusyId(null);
      operation.current = false;
    }
  };
  const completeStep = (step: PlanStep) => {
    const key = stepKey(step);
    const next = new Set(completed);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setCompleted(next);
    setAssistant(
      next.has(key) ? "completed" : plan?.feasible ? "ready" : "no-plan",
    );
    const upcoming = plan?.steps.find(
      (s) => s.type !== "note" && !next.has(stepKey(s)),
    );
    setGuideMessage(
      next.has(key)
        ? upcoming
          ? `Done. Next: ${upcoming.title.toLowerCase()}.`
          : "You’ve completed the steps in this plan. You can revisit any resource details here."
        : undefined,
    );
  };
  const stage = plan ? 2 : constraints ? 1 : 0;
  const completedCount =
    plan?.steps.filter((s) => s.type !== "note" && completed.has(stepKey(s)))
      .length ?? 0;
  const actionableCount =
    plan?.steps.filter((s) => s.type !== "note").length ?? 0;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to planner
      </a>
      <Header onOpenAdmin={() => setAdminOpen(true)} />
      <main id="main" className="main-shell">
        <div className="page-intro">
          <div>
            <div className="eyebrow">COMMUNITY SUPPORT, CONNECTED</div>
            <h1>A clearer path to help.</h1>
            <p>Let’s turn what you need into what you can do next.</p>
          </div>
          <div className="demo-clock">
            <Icon name="clock" size={18} />
            <div>
              Thursday, September 17
              <small>Demo starts at 6:00 PM · Baltimore time</small>
            </div>
          </div>
        </div>
        <ol className="journey" aria-label="Planning progress">
          {["Your situation", "Review your details", "Your action plan"].map(
            (label, i) => (
              <li
                key={label}
                className={i === stage ? "current" : i < stage ? "passed" : ""}
                aria-current={i === stage ? "step" : undefined}
              >
                <span>
                  {i < stage ? <Icon name="check" size={14} /> : `0${i + 1}`}
                </span>
                {label}
                {i < 2 && <div className="journey-line" />}
              </li>
            ),
          )}
        </ol>
        <div className={`planner-layout ${constraints ? "has-context" : ""}`}>
          <div className="context-column">
            {constraints && (
              <button
                className="mobile-context-toggle"
                onClick={() => setContextOpen(!contextOpen)}
                aria-expanded={contextOpen}
                aria-controls="situation-details"
              >
                <Icon name="edit" size={17} />
                {contextOpen
                  ? "Hide situation & details"
                  : "Your situation & details"}
                <Icon name="chevron" size={17} />
              </button>
            )}
            <div
              id="situation-details"
              className={`context-content ${contextOpen ? "expanded" : ""}`}
            >
              <SituationInput
                text={text}
                onTextChange={setSituation}
                phase={phase}
                error={!constraints ? error : null}
                onSubmit={() => void understand()}
                details={details}
                onPatch={(patch) =>
                  setOverrides((old) => ({ ...old, ...patch }))
                }
                onNeeds={setNeedOverrides}
                onDeadline={setDeadlineOverride}
                deadlineValue={deadlineOverride}
              />
              {constraints && phase !== "review" && (
                <ConstraintsPanel
                  constraints={constraints}
                  onEdit={() => {
                    if (!busy) setEdit(structuredClone(constraints));
                  }}
                />
              )}
            </div>
          </div>
          <div className="plan-column" ref={planColumn}>
            <Assistant
              state={assistant}
              message={guideMessage}
              reviewing={phase === "review" && !error}
            />
            {resourceError && !adminOpen && (
              <div className="alert error" role="alert">
                {resourceError}
                <button
                  className="text-button"
                  onClick={() => {
                    void getResources()
                      .then((list) => {
                        setResources(list);
                        setResourceError(null);
                      })
                      .catch((err) => setResourceError(errorMessage(err)));
                  }}
                >
                  Retry resource connection
                </button>
              </div>
            )}
            {!constraints && (
              <section className="empty-plan">
                <div className="empty-label">
                  <Icon name="route" size={18} />
                  YOUR NEXT STEPS, CONNECTED
                </div>
                <div className="empty-path" aria-hidden="true">
                  <span>
                    <Icon name="food" size={28} />
                  </span>
                  <i />
                  <span>
                    <Icon name="home" size={32} />
                  </span>
                  <i />
                  <span>
                    <Icon name="support" size={28} />
                  </span>
                </div>
                <h2>
                  You don’t have to figure
                  <br />
                  it all out at once.
                </h2>
                <p>
                  Tell us a little about your situation.
                  <br />
                  We’ll connect the resources into a plan you can follow.
                </p>
                <div className="empty-checks">
                  <span>
                    <Icon name="check" size={16} />
                    Fits your budget
                  </span>
                  <span>
                    <Icon name="check" size={16} />
                    Checks opening hours
                  </span>
                  <span>
                    <Icon name="check" size={16} />
                    Accounts for getting there
                  </span>
                </div>
                <div className="empty-bottom">
                  <span className="tiny-dot" />
                  One step at a time. Room to change course.
                </div>
              </section>
            )}
            {constraints && !plan && (
              <section className="review-area">
                <h2 ref={reviewHeading} tabIndex={-1} className="sr-only">
                  Review your details
                </h2>
                <ConstraintsPanel
                  constraints={constraints}
                  reviewing
                  onEdit={() => {
                    if (!busy) setEdit(structuredClone(constraints));
                  }}
                />
                {error && (
                  <p role="alert" className="alert error">
                    {error}
                  </p>
                )}
                <div className="review-actions">
                  <p>You can change these at any time.</p>
                  <button
                    className="button button-primary"
                    disabled={busy || !constraints.needs.length}
                    onClick={() => void build(constraints)}
                  >
                    {busy ? <Spinner /> : null}Find My Options
                    <Icon name="arrow" />
                  </button>
                </div>
              </section>
            )}
            {plan && (
              <>
                <h2 ref={reviewHeading} tabIndex={-1} className="sr-only">
                  Your action plan
                </h2>
                {bundle?.diff && (
                  <ReplanBanner
                    diff={bundle.diff}
                    resources={resources}
                    onDismiss={() =>
                      setBundle((old) => (old ? { ...old, diff: null } : null))
                    }
                  />
                )}
                {error && (
                  <p className="alert error" role="alert">
                    {error}
                    <button
                      className="text-button"
                      onClick={() => void build(plan.constraints, plan)}
                      disabled={busy}
                    >
                      Retry planning
                    </button>
                  </p>
                )}
                {invalidated || busy ? (
                  <div className="panel invalid-plan" role="status">
                    <Spinner />
                    <h2>
                      {busy
                        ? "Checking a new route…"
                        : "This route needs to be checked again"}
                    </h2>
                    <p>
                      The previous route is on hold until availability is
                      confirmed.
                    </p>
                  </div>
                ) : (
                  <>
                    <PlanComparison
                      plans={bundle!.plans}
                      selected={selected}
                      note={bundle!.alternatives_note}
                      onSelect={(id) => {
                        setSelected(id);
                        setCompleted(
                          (old) =>
                            new Set(
                              bundle!.plans
                                .find((p) => p.plan_id === id)!
                                .steps.map(stepKey)
                                .filter((key) => old.has(key)),
                            ),
                        );
                        setBundle((old) =>
                          old ? { ...old, diff: null } : null,
                        );
                        setAssistant(
                          bundle!.plans.find((p) => p.plan_id === id)!.feasible
                            ? "ready"
                            : "no-plan",
                        );
                        setGuideMessage(undefined);
                      }}
                    />
                    <div className="plan-overview">
                      <div>
                        <span>Estimated total</span>
                        <strong>
                          {formatUsd(plan.total_cost_usd)}
                          <small>
                            {plan.constraints.constraints.budget_usd !== null
                              ? ` / $${plan.constraints.constraints.budget_usd} budget`
                              : " · budget not specified"}
                          </small>
                        </strong>
                      </div>
                      <div>
                        <span>Total travel</span>
                        <strong>
                          {plan.total_travel_min}
                          <small> minutes</small>
                        </strong>
                      </div>
                      <div>
                        <span>Your progress</span>
                        <strong>
                          {completedCount}
                          <small> / {actionableCount} steps</small>
                        </strong>
                      </div>
                    </div>
                    <section className="map-section">
                      <button
                        className="map-toggle"
                        onClick={() => setShowMap(!showMap)}
                        aria-expanded={showMap}
                      >
                        <Icon name="pin" size={18} />
                        {showMap ? "Hide" : "Show"} route overview
                        <Icon name="chevron" size={17} />
                      </button>
                      {showMap && (
                        <>
                          <p className="small muted">
                            OpenStreetMap base map. Lines are approximate demo
                            connections, not turn-by-turn routes. Use Directions
                            for navigation.
                          </p>
                          <PlanMap
                            plan={plan}
                            resources={resources}
                            previousPlan={null}
                          />
                        </>
                      )}
                    </section>
                    <Timeline
                      plan={plan}
                      resources={resources}
                      updating={false}
                      highlightIds={bundle?.diff?.added_resource_ids ?? []}
                      completed={completed}
                      onComplete={completeStep}
                      onDetails={(r) => setDetailId(r.id)}
                    />
                    <RejectedPanel rejected={plan.rejected} />
                  </>
                )}
              </>
            )}
          </div>
        </div>
        <footer className="site-footer">
          <span className="brand-mini">AidGraph</span>
          <span>Community resources. A plan that connects them.</span>
          <span>Baltimore · Hackathon prototype</span>
        </footer>
      </main>
      <Modal
        open={!!edit}
        onClose={() => setEdit(null)}
        title="Edit your details"
      >
        {edit && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const updated = edit;
              setEdit(null);
              setConstraints(updated);
              setBundle(null);
              setCompleted(new Set());
              setPhase("review");
              setContextOpen(false);
              setError(null);
              setAssistant("warning");
              setGuideMessage(
                "Your changes are saved. Find your options to check the updated route.",
              );
            }}
          >
            <ConstraintFields
              value={edit}
              onPatch={(patch) =>
                setEdit((old) =>
                  old
                    ? { ...old, constraints: { ...old.constraints, ...patch } }
                    : null,
                )
              }
              onNeeds={(needs) =>
                setEdit((old) => (old ? { ...old, needs } : null))
              }
            />
            <details className="priority-editor">
              <summary>Adjust individual priorities and deadlines</summary>
              {edit.needs.map((n) => (
                <div className="priority-row" key={n.type}>
                  <strong>{SERVICE_LABEL[n.type]}</strong>
                  <label>
                    Priority
                    <select
                      value={n.priority}
                      onChange={(e) =>
                        setEdit((old) =>
                          old
                            ? {
                                ...old,
                                needs: old.needs.map((item) =>
                                  item.type === n.type
                                    ? {
                                        ...item,
                                        priority: e.target
                                          .value as Need["priority"],
                                      }
                                    : item,
                                ),
                              }
                            : null,
                        )
                      }
                    >
                      {["high", "medium", "low"].map((p) => (
                        <option key={p}>{p}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Deadline
                    <select
                      value={n.deadline}
                      onChange={(e) =>
                        setEdit((old) =>
                          old
                            ? {
                                ...old,
                                needs: old.needs.map((item) =>
                                  item.type === n.type
                                    ? {
                                        ...item,
                                        deadline: e.target
                                          .value as Need["deadline"],
                                      }
                                    : item,
                                ),
                              }
                            : null,
                        )
                      }
                    >
                      {Object.entries(DEADLINE_LABEL).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
            </details>
            <div className="modal-footer">
              <button
                type="button"
                className="button"
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button
                className="button button-primary"
                disabled={!edit.needs.length}
                type="submit"
              >
                Save details
                <Icon name="check" size={17} />
              </button>
            </div>
          </form>
        )}
      </Modal>
      <ResourceDetails
        resource={resources.find((r) => r.id === detailId) ?? null}
        onClose={() => setDetailId(null)}
        mode={
          plan?.steps.find(
            (s) => s.type === "travel" && s.resource_id === detailId,
          )?.mode
        }
      />
      <AdminDrawer
        open={adminOpen}
        onClose={() => setAdminOpen(false)}
        resources={resources}
        busyId={adminBusyId}
        disabled={busy}
        error={resourceError}
        activeIds={plan?.resource_ids ?? []}
        onChangeStatus={(id, status) => void updateAvailability(id, status)}
        onReset={() => void updateAvailability()}
      />
    </div>
  );
}
