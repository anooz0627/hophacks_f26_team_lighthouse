"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import AdminDrawer from "@/components/AdminDrawer";
import { type AssistantState } from "@/components/Assistant";
import ConstraintFields from "@/components/ConstraintFields";
import ConstraintsPanel from "@/components/ConstraintsPanel";
import Header from "@/components/Header";
import ListenButton from "@/components/ListenButton";
import DisruptionInput, { type ChangeMessage } from "@/components/DisruptionInput";
import NowCard from "@/components/NowCard";
import BlockedNeeds from "@/components/BlockedNeeds";
import HelpCard from "@/components/HelpCard";
import LocationEditor from "@/components/LocationEditor";
import Icon from "@/components/Icon";
import Modal from "@/components/Modal";
import PlanComparison from "@/components/PlanComparison";
import RejectedPanel from "@/components/RejectedPanel";
import ReplanBanner from "@/components/ReplanBanner";
import ResourceDetails from "@/components/ResourceDetails";
import SituationInput, { type Phase } from "@/components/SituationInput";
import Timeline, { stepKey } from "@/components/Timeline";
import UnroutedResources from "@/components/UnroutedResources";
import { Spinner } from "@/components/ui";
import {
  extract,
  generatePlans,
  getHealth,
  getResources,
  getTransit,
  reportDisruption,
  setTransitDelay,
  setResourceStatus,
  resetResources,
  errorMessage,
} from "@/lib/api";
import { DEFAULT_CONSTRAINTS, emptyConstraints } from "@/lib/constraints";
import { formatUsd, SERVICE_LABEL, DEADLINE_LABEL } from "@/lib/format";
import useCurrentLocation from "@/lib/useCurrentLocation";
import type {
  Constraints,
  Deadline,
  Health,
  Need,
  Plan,
  PlanBundle,
  PlanStep,
  Progress,
  TransitRoute,
  Resource,
  ResourceStatus,
  UserConstraints,
} from "@/lib/types";
const PlanMap = dynamic(() => import("@/components/PlanMap"), {
  ssr: false,
  loading: () => <p className="muted">Loading map…</p>,
});

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
  const [health, setHealth] = useState<Health | null>(null);
  const [transit, setTransit] = useState<TransitRoute[]>([]);
  const [helpOpen, setHelpOpen] = useState(false);
  const [changeHistory, setChangeHistory] = useState<ChangeMessage[]>([]);
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [edit, setEdit] = useState<UserConstraints | null>(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [locationOpen, setLocationOpen] = useState(false);
  const [adminBusyId, setAdminBusyId] = useState<string | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [, setAssistant] = useState<AssistantState>("idle");
  const [, setGuideMessage] = useState<string | undefined>();
  const [invalidated, setInvalidated] = useState(false);
  const [stage, setStage] = useState(0);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const {
    location,
    retry: retryLocation,
    selectAddress,
  } = useCurrentLocation();
  const planColumn = useRef<HTMLDivElement>(null);
  const [showMap, setShowMap] = useState(true);
  const operation = useRef(false);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const previousStage = useRef(0);
  const plan =
    bundle?.plans.find((p) => p.plan_id === selected) ??
    bundle?.plans[0] ??
    null;
  const busy =
    voiceBusy || ["extracting", "planning", "replanning"].includes(phase);
  const details = constraints ?? {
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
    getHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {});
    getTransit()
      .then((routes) => {
        if (!cancelled) setTransit(routes);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    if (previousStage.current === stage) return;
    previousStage.current = stage;
    if (stage === 0) {
      document
        .getElementById("situation-heading")
        ?.focus({ preventScroll: true });
    } else {
      reviewHeading.current?.focus({ preventScroll: true });
      planColumn.current?.scrollIntoView({ block: "start" });
    }
  }, [stage]);

  const setSituation = (value: string, example = false) => {
    setText(value);
    setStage(0);
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
    if (operation.current || voiceBusy || !text.trim()) return;
    if (constraints) {
      setStage(1);
      setPhase("review");
      setAssistant("warning");
      setGuideMessage("Check your details before finding your options.");
      return;
    }
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
        constraints: {
          ...uc.constraints,
          ...overrides,
          current_location: location.coordinates,
          location_label:
            location.address ?? location.label ?? "Current location",
        },
        needs: (needOverrides ?? uc.needs).map((n) =>
          deadlineOverride &&
          (n.type !== "long_term_assistance" ||
            (needOverrides ?? uc.needs).length === 1)
            ? { ...n, deadline: deadlineOverride }
            : n,
        ),
      };
      setConstraints(reviewed);
      setStage(1);
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
  const actionable = plan?.steps.filter((s) => s.type !== "note") ?? [];
  const nextStep = actionable.find((s) => !completed.has(stepKey(s))) ?? null;
  const nextResource = resources.find((r) => r.id === nextStep?.resource_id);
  const doneCount = actionable.filter((s) => completed.has(stepKey(s))).length;
  const [disruptionOpen, setDisruptionOpen] = useState(false);
  const focusDisruption = () => setDisruptionOpen(true);
  const longWalk =
    plan?.steps.find((s) => s.warnings.some((w) => w.startsWith("Long walk"))) ??
    null;
  const progressFor = (current: Plan): Progress => ({
    completed_orders: current.steps
      .filter((s) => completed.has(stepKey(s)))
      .map((s) => s.order),
    current_location: null,
    now: null,
  });
  const handleDisruption = async (message: string) => {
    const current = plan;
    if (!current || operation.current || voiceBusy) return;
    operation.current = true;
    setError(null);
    setPhase("replanning");
    setAssistant("replanning");
    setGuideMessage(undefined);
    setChangeHistory((history) => [...history, { role: "user", text: message }]);
    try {
      const [next, list, routes] = await Promise.all([
        reportDisruption(current.plan_id, message, progressFor(current)),
        getResources(),
        getTransit(),
      ]);
      setResources(list);
      setTransit(routes);
      acceptBundle(next, current);
      setChangeHistory((history) => [...history, { role: "assistant", text: next.message }]);
      setGuideMessage(next.message);
    } catch (err) {
      setError(errorMessage(err));
      setChangeHistory((history) => [...history, { role: "assistant", text: `Could not update the plan: ${errorMessage(err)}`, error: true }]);
      setPhase("planned");
      setAssistant("warning");
    } finally {
      operation.current = false;
    }
  };
  const updateDelay = async (routeId: string, minutes: number) => {
    if (operation.current || voiceBusy) return;
    operation.current = true;
    setAdminBusyId(routeId);
    setResourceError(null);
    const current = plan;
    if (current) {
      setPhase("replanning");
      setAssistant("replanning");
      setGuideMessage(undefined);
    }
    try {
      const updated = await setTransitDelay(routeId, minutes);
      setTransit((list) => list.map((r) => (r.id === routeId ? updated : r)));
      if (current) {
        const next = await generatePlans(
          current.constraints,
          undefined,
          current.plan_id,
          progressFor(current),
        );
        if (next.diff)
          next.diff.trigger =
            minutes > 0
              ? `${updated.name} is delayed ${minutes} min`
              : `${updated.name} is back on time`;
        acceptBundle(next, current);
      }
    } catch (err) {
      setResourceError(errorMessage(err));
      if (current) {
        setPhase("planned");
        setAssistant("warning");
      }
    } finally {
      setAdminBusyId(null);
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
    setStage(2);
    setCompleted((old) =>
      previous
        ? new Set(active.steps.map(stepKey).filter((key) => old.has(key)))
        : new Set(),
    );
    setAssistant(active.feasible ? "ready" : "no-plan");
    const walkWarning = active.steps
      .flatMap((s) => s.warnings)
      .find((w) => w.startsWith("Long walk"));
    setGuideMessage(
      walkWarning
        ? `${walkWarning.replace(" Tell us below if that is too far.", "")} Is that OK? If not, tell me below and I will look for shorter options.`
        : undefined,
    );
  };
  const build = async (uc: UserConstraints, previous?: Plan) => {
    if (operation.current || voiceBusy) return;
    if (!location.coordinates) {
      setError("Allow location access before finding your options.");
      return;
    }
    operation.current = true;
    setError(null);
    setPhase(previous ? "replanning" : "planning");
    setAssistant(previous ? "replanning" : "building");
    setGuideMessage(undefined);
    try {
      const [next, list] = await Promise.all([
        generatePlans(
          {
            ...uc,
            constraints: {
              ...uc.constraints,
              current_location: location.coordinates,
              location_label:
                location.address ?? location.label ?? "Current location",
            },
          },
          undefined,
          previous?.plan_id,
        ),
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
    if (operation.current || voiceBusy) return;
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
      } else {
        setResources(await resetResources());
        setTransit(await getTransit());
      }
      if (current) {
        const next = await generatePlans(
          current.constraints,
          undefined,
          current.plan_id,
          progressFor(current),
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
  const changeDetails = (patch: Partial<Constraints>) => {
    setOverrides((old) => ({ ...old, ...patch }));
    setConstraints((old) =>
      old ? { ...old, constraints: { ...old.constraints, ...patch } } : null,
    );
    setBundle(null);
    setCompleted(new Set());
  };
  const changeNeeds = (needs: Need[]) => {
    setNeedOverrides(needs);
    setConstraints((old) => (old ? { ...old, needs } : null));
    setBundle(null);
    setCompleted(new Set());
  };
  const navigate = (next: number) => {
    if (busy || (next === 1 && !constraints) || (next === 2 && !plan)) return;
    setStage(next);
    setError(null);
    setPhase(next === 0 ? "idle" : next === 1 ? "review" : "planned");
    setAssistant(
      next === 0
        ? "idle"
        : next === 1
          ? "warning"
          : plan?.feasible
            ? "ready"
            : "no-plan",
    );
    setGuideMessage(undefined);
  };
  const locationDetails = constraints
    ? {
        ...constraints,
        constraints: {
          ...constraints.constraints,
          current_location: location.coordinates,
          location_label:
            location.address ?? location.label ?? "Current location",
        },
      }
    : null;
  const invalidateLocationPlan = () => {
    setBundle(null);
    setCompleted(new Set());
    setInvalidated(false);
    setError(null);
    if (stage === 2) navigate(1);
    setLocationOpen(false);
  };
  const refreshLocation = () => {
    invalidateLocationPlan();
    retryLocation();
  };
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
      <Header
        onOpenAdmin={() => setAdminOpen(true)}
        location={location}
        busy={busy}
        onLocate={() => setLocationOpen(true)}
      />
      <main id="main" className="main-shell">
        <div className="page-intro">
          <div>
            <div className="eyebrow">COMMUNITY SUPPORT, CONNECTED</div>
            <h1>A clearer path to help.</h1>
            <p>Let’s turn what you need into what you can do next.</p>
          </div>
        </div>
        <div
          className={`location-status location-${location.status}`}
          id="location-status"
          role="status"
        >
          <Icon name="pin" size={18} />
          <p>{location.message}</p>
          {location.status === "error" && (
            <button
              className="text-button"
              onClick={refreshLocation}
              disabled={busy}
            >
              Try again
            </button>
          )}
          {location.status === "error" && (
            <button
              className="text-button"
              onClick={() => setLocationOpen(true)}
              disabled={busy}
            >
              Use another address instead
            </button>
          )}
        </div>
        <ol className="journey" aria-label="Planning progress">
          {["Your situation", "Review your details", "Your action plan"].map(
            (label, i) => (
              <li
                key={label}
                className={i === stage ? "current" : i < stage ? "passed" : ""}
                aria-current={i === stage ? "step" : undefined}
              >
                <button
                  type="button"
                  onClick={() => navigate(i)}
                  disabled={
                    busy || (i === 1 && !constraints) || (i === 2 && !plan)
                  }
                  aria-current={i === stage ? "step" : undefined}
                >
                  <span>
                    {i < stage ? <Icon name="check" size={14} /> : `0${i + 1}`}
                  </span>
                  {label}
                </button>
                {i < 2 && <div className="journey-line" />}
              </li>
            ),
          )}
        </ol>
        <div
          className={`planner-layout planner-flow ${stage === 0 ? "situation-flow" : ""}`}
        >
          <div className="plan-column" ref={planColumn}>
            {stage > 0 && (
              <button
                type="button"
                className="button button-quiet back-button"
                disabled={busy}
                onClick={() => navigate(stage - 1)}
              >
                <Icon name="back" size={18} /> Back to{" "}
                {stage === 1 ? "your situation" : "review your details"}
              </button>
            )}
            {stage === 0 && (
              <SituationInput
                text={text}
                onTextChange={setSituation}
                phase={phase}
                error={error}
                onSubmit={() => void understand()}
                details={details}
                onPatch={changeDetails}
                onNeeds={changeNeeds}
                onDeadline={(deadline) => {
                  setDeadlineOverride(deadline);
                  if (constraints)
                    changeNeeds(
                      constraints.needs.map((need) =>
                        need.type !== "long_term_assistance" ||
                        constraints.needs.length === 1
                          ? { ...need, deadline }
                          : need,
                      ),
                    );
                }}
                deadlineValue={deadlineOverride}
                voiceAvailable={!!health?.voice}
                voiceBusy={voiceBusy}
                onVoiceBusy={setVoiceBusy}
                onTranscript={(transcript) => {
                  const next = [text.trim(), transcript.trim()]
                    .filter(Boolean)
                    .join(" ");
                  if (next.length > 10000)
                    throw new Error(
                      "There isn’t enough room for this recording. Shorten your text and try again.",
                    );
                  setSituation(next);
                }}
              />
            )}
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
            {stage === 0 && (
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
                  We’ll turn them into a plan you can follow, one step at a time.
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
            {stage === 1 && constraints && (
              <section className="review-area">
                <h2 ref={reviewHeading} tabIndex={-1} className="sr-only">
                  Review your details
                </h2>
                <ConstraintsPanel
                  constraints={locationDetails!}
                  reviewing
                  onEditLocation={() => {
                    if (!busy) setLocationOpen(true);
                  }}
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
                    disabled={
                      busy || !constraints.needs.length || !location.coordinates
                    }
                    onClick={() =>
                      plan && !invalidated
                        ? navigate(2)
                        : void build(constraints)
                    }
                  >
                    {busy ? <Spinner /> : null}
                    {plan && !invalidated
                      ? "Return to my plan"
                      : "Find My Options"}
                    <Icon name="arrow" />
                  </button>
                </div>
              </section>
            )}
            {stage === 2 && plan && (
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
                    <DisruptionInput
                      open={disruptionOpen}
                      onOpenChange={setDisruptionOpen}
                      onSubmit={(t) => void handleDisruption(t)}
                      busy={busy}
                      messages={changeHistory}
                      suggestions={longWalk ? ["That's too far to walk"] : []}
                    />
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
                    <NowCard
                      step={nextStep}
                      resource={nextResource}
                      done={doneCount}
                      total={actionable.length}
                      onDone={() => nextStep && completeStep(nextStep)}
                      onStuck={focusDisruption}
                      onShowCard={() => setHelpOpen(true)}
                    />
                    <BlockedNeeds
                      blocked={plan.blocked ?? []}
                      resources={resources}
                      onDetails={(r) => setDetailId(r.id)}
                      onStuck={focusDisruption}
                    />
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
                    {health?.voice && (
                      <ListenButton
                        key={plan.plan_id}
                        planId={plan.plan_id}
                        contactsOnly={
                          !plan.resource_ids.length &&
                          !!plan.unrouted_resources?.length
                        }
                      />
                    )}
                    <UnroutedResources
                      plan={plan}
                      resources={resources}
                      onDetails={(resource) => setDetailId(resource.id)}
                      onEditLocation={() => setLocationOpen(true)}
                      onEditDetails={() =>
                        setEdit(structuredClone(plan.constraints))
                      }
                    />
                    {plan.resource_ids.length > 0 && (
                      <>
                        <div className="plan-overview">
                          <div>
                            <span>Estimated total</span>
                            <strong>
                              {formatUsd(plan.total_cost_usd)}
                              <small>
                                {plan.constraints.constraints.budget_usd !==
                                null
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
                                OpenStreetMap base map. Lines are approximate
                                demo connections, not turn-by-turn routes. Use
                                Directions for navigation.
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
                      </>
                    )}
                    <RejectedPanel rejected={plan.rejected} />

                  </>
                )}
              </>
            )}
          </div>
        </div>
        <footer className="site-footer">
          <span className="brand-mini">Lighthouse</span>
          <span>Community resources. A light to guide you there.</span>
          <span>Baltimore · Hackathon prototype</span>
        </footer>
      </main>
      <LocationEditor
        open={locationOpen}
        location={location}
        onClose={() => setLocationOpen(false)}
        onUseCurrent={refreshLocation}
        onSelect={(match) => {
          invalidateLocationPlan();
          selectAddress(match);
        }}
      />
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
              const changed =
                JSON.stringify(updated) !== JSON.stringify(constraints);
              if (changed) {
                setBundle(null);
                setCompleted(new Set());
                const changedFields = Object.fromEntries(
                  Object.entries(updated.constraints).filter(
                    ([key, value]) =>
                      JSON.stringify(value) !==
                      JSON.stringify(
                        constraints?.constraints[key as keyof Constraints],
                      ),
                  ),
                );
                setOverrides((old) => ({ ...old, ...changedFields }));
                if (
                  JSON.stringify(updated.needs) !==
                  JSON.stringify(constraints?.needs)
                ) {
                  setNeedOverrides(updated.needs);
                  setDeadlineOverride(undefined);
                }
              }
              setPhase("review");
              setStage(1);
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
        origin={
          plan?.constraints.constraints.current_location ?? location.coordinates
        }
        onClose={() => setDetailId(null)}
        mode={
          plan?.steps.find(
            (s) => s.type === "travel" && s.resource_id === detailId,
          )?.mode
        }
      />
      {plan && (
        <HelpCard
          open={helpOpen}
          onClose={() => setHelpOpen(false)}
          plan={plan}
          step={nextStep}
          resource={nextResource}
          voice={health?.voice ?? false}
        />
      )}
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
        transit={transit}
        onChangeDelay={(id, minutes) => void updateDelay(id, minutes)}
      />
    </div>
  );
}
