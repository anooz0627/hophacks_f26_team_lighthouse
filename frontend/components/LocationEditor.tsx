"use client";
import { useEffect, useRef, useState } from "react";
import { errorMessage, searchAddresses } from "@/lib/api";
import type { AddressMatch } from "@/lib/types";
import type { LocationState } from "@/lib/useCurrentLocation";
import Icon from "./Icon";
import Modal from "./Modal";

export default function LocationEditor({
  open,
  location,
  onClose,
  onUseCurrent,
  onSelect,
}: {
  open: boolean;
  location: LocationState;
  onClose: () => void;
  onUseCurrent: () => void;
  onSelect: (match: AddressMatch) => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Change your starting location">
      {open && (
        <AddressForm
          location={location}
          onUseCurrent={onUseCurrent}
          onSelect={onSelect}
        />
      )}
    </Modal>
  );
}

function AddressForm({
  location,
  onUseCurrent,
  onSelect,
}: {
  location: LocationState;
  onUseCurrent: () => void;
  onSelect: (match: AddressMatch) => void;
}) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<AddressMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  return (
    <div className="location-editor">
      {location.coordinates && (
        <p className="current-address">
          <strong>Starting from</strong>
          <span>{location.address ?? location.label}</span>
        </p>
      )}
      <button
        type="button"
        className="button"
        onClick={onUseCurrent}
        disabled={location.status === "locating"}
      >
        <Icon name="pin" size={18} /> Use my current location
      </button>
      <p className="field-hint">
        This requests a fresh GPS position. If access is already allowed, your
        browser may not ask again.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (busy || query.trim().length < 3) return;
          controller.current?.abort();
          const request = new AbortController();
          controller.current = request;
          setBusy(true);
          setError(null);
          setMatches(null);
          try {
            const results = await searchAddresses(query.trim(), request.signal);
            if (!request.signal.aborted) setMatches(results);
          } catch (err) {
            if (!request.signal.aborted) setError(errorMessage(err));
          } finally {
            if (!request.signal.aborted) setBusy(false);
          }
        }}
      >
        <h3>Use another address instead</h3>
        <label className="field">
          Street address
          <input
            value={query}
            minLength={3}
            maxLength={100}
            required
            autoComplete="street-address"
            placeholder="400 W Lexington St, Baltimore, MD"
            onChange={(event) => {
              controller.current?.abort();
              setBusy(false);
              setQuery(event.target.value);
              setMatches(null);
              setError(null);
            }}
          />
        </label>
        <p className="field-hint">
          Include a house number, street and city or ZIP code. Your search is
          sent to the U.S. Census address service.
        </p>
        <button
          type="submit"
          className="button button-primary"
          disabled={busy || query.trim().length < 3}
        >
          {busy ? "Searching addresses…" : "Find address"}
        </button>
      </form>
      <div role="status">
        {error && <p className="alert error">{error}</p>}
        {matches?.length === 0 && (
          <p>
            No matching address found. Check the house number and include a city
            or ZIP code.
          </p>
        )}
      </div>
      {!!matches?.length && (
        <div className="address-results">
          <p>Choose the matching address to use it as your starting point.</p>
          <ul>
            {matches.map((match) => (
              <li key={`${match.coordinates.lat},${match.coordinates.lng}`}>
                <p>{match.address}</p>
                <button
                  type="button"
                  className="button"
                  onClick={() => onSelect(match)}
                >
                  Use this address <Icon name="arrow" size={17} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
