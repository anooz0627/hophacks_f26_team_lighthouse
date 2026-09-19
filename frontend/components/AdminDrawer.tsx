"use client";

import type { Resource, ResourceStatus } from "@/lib/types";
import { STATUS_LABEL, STATUS_OPTIONS, SERVICE_LABEL } from "@/lib/format";
import Icon from "./Icon";
import Modal from "./Modal";

export default function AdminDrawer({
  open,
  onClose,
  resources,
  busyId,
  disabled,
  error,
  onChangeStatus,
  onReset,
  activeIds,
}: {
  open: boolean;
  onClose: () => void;
  resources: Resource[];
  busyId: string | null;
  disabled: boolean;
  error: string | null;
  onChangeStatus: (id: string, status: ResourceStatus) => void;
  onReset: () => void;
  activeIds: string[];
}) {
  const shelter = resources.find(
    (r) => activeIds.includes(r.id) && r.service === "emergency_housing",
  );
  const locked = disabled || busyId !== null;
  return (
    <Modal open={open} onClose={onClose} title="Simulate availability" wide>
      <p className="muted">
        Changes apply to this local demo server. Your plan is checked again
        automatically.
      </p>
      {error && (
        <p className="alert error" role="alert">
          {error}
        </p>
      )}
      {shelter && (
        <div className="demo-shortcut">
          <div>
            <span className="eyebrow">SHELTER IN YOUR PLAN</span>
            <strong>{shelter.name}</strong>
          </div>
          <button
            className="button button-primary"
            disabled={locked || shelter.status === "full"}
            onClick={() => onChangeStatus(shelter.id, "full")}
          >
            <Icon name="route" size={17} />
            Mark selected shelter full
          </button>
        </div>
      )}
      <div className="demo-toolbar">
        <span>{resources.length} illustrative resources</span>
        <button className="text-button" onClick={onReset} disabled={locked}>
          Reset demo availability
        </button>
      </div>
      <div className="status-list">
        {resources.map((r) => (
          <div
            className={`status-row ${activeIds.includes(r.id) ? "in-plan" : ""}`}
            key={r.id}
          >
            <div>
              <strong>{r.name}</strong>
              <small>
                {SERVICE_LABEL[r.service]}
                {activeIds.includes(r.id) ? " · In your plan" : ""}
              </small>
            </div>
            <label>
              <span className="sr-only">Status for {r.name}</span>
              <select
                value={r.status}
                disabled={locked}
                onChange={(e) =>
                  onChangeStatus(r.id, e.target.value as ResourceStatus)
                }
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {STATUS_LABEL[status]}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
      </div>
    </Modal>
  );
}
