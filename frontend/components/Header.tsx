"use client";
import Link from "next/link";
import Icon from "./Icon";
import type { LocationState } from "@/lib/useCurrentLocation";
export default function Header({
  onOpenAdmin,
  location,
  onLocate,
  busy,
}: {
  onOpenAdmin: () => void;
  location: LocationState;
  onLocate: () => void;
  busy: boolean;
}) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="Lighthouse home">
          <span className="brand-mark">
            <Icon name="lighthouse" size={24} />
          </span>
          Light<span>house</span>
        </Link>
        <button
          className="region location-button"
          onClick={onLocate}
          disabled={busy}
          aria-haspopup="dialog"
          title="Change starting location"
          aria-describedby="location-status"
        >
          <Icon name="pin" size={16} />
          {location.status === "ready"
            ? (location.label ?? "Finding your postal code…")
            : location.status === "locating"
              ? "Finding your location…"
              : "Retry location"}
        </button>
        <div className="header-actions">
          <button
            className="button button-quiet"
            onClick={onOpenAdmin}
            disabled={busy}
          >
            <Icon name="settings" size={17} />
            <span>Availability</span>
          </button>
        </div>
      </div>
    </header>
  );
}
