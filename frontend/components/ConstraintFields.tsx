"use client";
import { useId } from "react";
import {
  ACCESSIBILITY,
  GENDERS,
  SUPPORT_DETAILS,
  TRANSPORT,
  needFor,
} from "@/lib/constraints";
import { SERVICE_LABEL } from "@/lib/format";
import type {
  Constraints,
  Deadline,
  Need,
  ServiceType,
  UserConstraints,
} from "@/lib/types";
import Icon from "./Icon";
export default function ConstraintFields({
  value,
  onPatch,
  onNeeds,
  disabled = false,
  onDeadline,
  deadlineValue,
}: {
  value: UserConstraints;
  onPatch: (patch: Partial<Constraints>) => void;
  onNeeds: (needs: Need[]) => void;
  disabled?: boolean;
  onDeadline?: (deadline: Deadline) => void;
  deadlineValue?: Deadline;
}) {
  const id = useId();
  const c = value.constraints;
  const otherMembers =
    c.other_household_members ?? (!c.children && c.family_size > 1);
  const minimumPeople = 1 + Number(c.children) + Number(otherMembers);
  const toggleNeed = (type: ServiceType) =>
    onNeeds(
      value.needs.some((n) => n.type === type)
        ? value.needs.filter((n) => n.type !== type)
        : [...value.needs, needFor(type)],
    );
  const deadline =
    deadlineValue ??
    value.needs.find((n) => n.type !== "long_term_assistance")?.deadline ??
    value.needs[0]?.deadline ??
    "tonight";
  return (
    <fieldset disabled={disabled} className="constraint-fields">
      <legend className="sr-only">Customize your needs and constraints</legend>
      <div className="field">
        <span className="field-label">What do you need help with?</span>
        <div className="chips">
          {(["emergency_housing", "food", "long_term_assistance"] as const).map(
            (type) => (
              <button
                key={type}
                type="button"
                className={`chip ${value.needs.some((n) => n.type === type) ? "selected" : ""}`}
                aria-pressed={value.needs.some((n) => n.type === type)}
                onClick={() => toggleNeed(type)}
              >
                {SERVICE_LABEL[type]}
              </button>
            ),
          )}
          <button
            type="button"
            className={`chip ${c.transportation_needed ? "selected" : ""}`}
            aria-pressed={c.transportation_needed}
            onClick={() =>
              onPatch({ transportation_needed: !c.transportation_needed })
            }
          >
            Transportation
          </button>
        </div>
        <p className="field-hint">
          Transportation is planned between your stops.
        </p>
      </div>
      <div className="field-grid">
        <label className="field" htmlFor={`${id}-age`}>
          Age
          <input
            id={`${id}-age`}
            type="number"
            inputMode="numeric"
            min="0"
            max="120"
            value={c.age ?? ""}
            placeholder="Not specified"
            onChange={(e) =>
              onPatch({
                age: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </label>
        <label className="field" htmlFor={`${id}-budget`}>
          Available budget ($)
          <input
            id={`${id}-budget`}
            type="number"
            inputMode="decimal"
            min="0"
            max="100000"
            step="0.01"
            placeholder="Not specified"
            value={c.budget_usd ?? ""}
            onChange={(e) =>
              onPatch({
                budget_usd:
                  e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </label>
      </div>
      <fieldset className="field">
        <legend className="field-label">Do you have photo ID?</legend>
        <div className="segmented">
          {[
            { label: "Yes", value: true },
            { label: "No", value: false },
            { label: "Unsure", value: null },
          ].map((option) => (
            <label key={option.label}>
              <input
                type="radio"
                name={`${id}-photo-id`}
                checked={c.has_id === option.value}
                onChange={() => onPatch({ has_id: option.value })}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field" htmlFor={`${id}-deadline`}>
        When do you need help?
        <select
          id={`${id}-deadline`}
          value={deadline}
          onChange={(e) => {
            const next = e.target.value as Deadline;
            if (onDeadline) {
              onDeadline(next);
              return;
            }
            const needs = value.needs.length
              ? value.needs
              : [needFor("emergency_housing")];
            onNeeds(
              needs.map((n) =>
                n.type === "long_term_assistance" && needs.length > 1
                  ? n
                  : { ...n, deadline: next },
              ),
            );
          }}
        >
          <option value="tonight">Tonight</option>
          <option value="within_24_hours">Within 24 hours</option>
          <option value="tomorrow">Tomorrow</option>
          <option value="this_week">This week</option>
          <option value="custom">Custom deadline</option>
        </select>
      </label>
      {(deadline === "custom" ||
        value.needs.some((n) => n.deadline === "custom")) && (
        <label className="field">
          Custom deadline (Baltimore time)
          <input
            type="datetime-local"
            required
            value={c.custom_deadline?.slice(0, 16) ?? ""}
            onInput={(e) =>
              onPatch({ custom_deadline: e.currentTarget.value || null })
            }
            onChange={(e) =>
              onPatch({ custom_deadline: e.target.value || null })
            }
          />
        </label>
      )}
      <fieldset className="support-fields">
        <legend>Getting there &amp; support</legend>
        <label className="field" htmlFor={`${id}-transport`}>
          How will you get there?
          <select
            id={`${id}-transport`}
            value={c.transport}
            onChange={(e) =>
              onPatch({
                transport: e.target.value as Constraints["transport"],
                has_car: e.target.value === "own_vehicle",
              })
            }
          >
            {Object.entries(TRANSPORT).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <p className="field-hint">
          Choose what would make the trip work for you. These choices affect
          which routes and places we can include.
        </p>
        {Object.entries(ACCESSIBILITY).map(([key, label]) => (
          <label className="support-option" key={key}>
            <input
              type="checkbox"
              checked={c.accessibility.includes(
                key as keyof typeof ACCESSIBILITY,
              )}
              onChange={(e) =>
                onPatch({
                  accessibility: e.target.checked
                    ? [...c.accessibility, key as keyof typeof ACCESSIBILITY]
                    : c.accessibility.filter((a) => a !== key),
                })
              }
            />
            <span>
              <strong>{label}</strong>
              <small>
                {SUPPORT_DETAILS[key as keyof typeof SUPPORT_DETAILS]}
              </small>
            </span>
          </label>
        ))}
        <p className="field-hint">
          Some providers haven’t confirmed their access information. If we can’t
          find a match, we’ll show what needs checking.
        </p>
      </fieldset>
      <fieldset className="field">
        <legend className="field-label">Who is coming with you?</legend>
        <label className="check-field">
          <input
            type="checkbox"
            checked={c.children}
            onChange={(e) =>
              onPatch({
                children: e.target.checked,
                other_household_members: otherMembers,
                family_size: e.target.checked
                  ? Math.max(minimumPeople + 1, Math.min(20, c.family_size + 1))
                  : otherMembers
                    ? Math.max(2, c.family_size - 1)
                    : 1,
              })
            }
          />
          Children
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            checked={otherMembers}
            onChange={(e) =>
              onPatch({
                other_household_members: e.target.checked,
                family_size: e.target.checked
                  ? Math.max(minimumPeople + 1, Math.min(20, c.family_size + 1))
                  : c.children
                    ? Math.max(2, c.family_size - 1)
                    : 1,
              })
            }
          />
          Other household members
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            checked={c.pets}
            onChange={(e) => onPatch({ pets: e.target.checked })}
          />
          Pets
        </label>
        <label className="field">
          Total people, including you
          <input
            type="number"
            min={minimumPeople}
            max="20"
            value={c.family_size}
            onChange={(e) => onPatch({ family_size: Number(e.target.value) })}
          />
        </label>
      </fieldset>
      <label className="field">
        Gender (optional)
        <select
          value={c.gender ?? ""}
          onChange={(e) =>
            onPatch({
              gender: (e.target.value || null) as Constraints["gender"],
              gender_description: null,
            })
          }
        >
          <option value="">Not specified</option>
          {Object.entries(GENDERS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <span className="field-hint">
          <Icon name="info" size={14} /> Only used to check services with a
          stated restriction.
        </span>
      </label>
      {c.gender === "self_describe" && (
        <label className="field">
          How do you describe your gender? (optional)
          <input
            maxLength={80}
            value={c.gender_description ?? ""}
            onChange={(e) =>
              onPatch({ gender_description: e.target.value || null })
            }
          />
        </label>
      )}
    </fieldset>
  );
}
