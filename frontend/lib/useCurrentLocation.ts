"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { AddressMatch, LatLng } from "./types";
import { getLocationLabel } from "./api";

export type LocationState = {
  status: "locating" | "ready" | "error";
  coordinates: LatLng | null;
  label: string | null;
  address?: string;
  message: string;
};

export default function useCurrentLocation() {
  const [location, setLocation] = useState<LocationState>({
    status: "locating",
    coordinates: null,
    label: null,
    message: "Allow location access to find a route from where you are.",
  });
  const requestId = useRef(0);
  const manuallySelected = useRef(false);
  const locate = useCallback((previous?: LocationState) => {
    const id = ++requestId.current;
    const update = (next: LocationState) => {
      if (
        id === requestId.current &&
        next.status === "error" &&
        previous?.address
      )
        manuallySelected.current = true;
      if (id === requestId.current)
        setLocation(
          next.status === "error" && previous?.coordinates
            ? {
                ...previous,
                message: `${next.message} Your previous starting location is still selected.`,
              }
            : next,
        );
    };
    if (!navigator.geolocation) {
      update({
        status: "error",
        coordinates: null,
        label: null,
        message:
          "This browser cannot access your location. Try a browser with location services enabled.",
      });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        if (id !== requestId.current) return;
        const coordinates = { lat: coords.latitude, lng: coords.longitude };
        update({
          status: "ready",
          coordinates,
          label: null,
          message: "Finding your postal code…",
        });
        try {
          const { label } = await getLocationLabel(coordinates);
          update({
            status: "ready",
            coordinates,
            label: label ?? "Outside Baltimore",
            message: label
              ? "Routes start at your current location. Resources currently cover Baltimore."
              : "Your location is outside our Baltimore service area. Nearby resources may not be available.",
          });
        } catch {
          update({
            status: "ready",
            coordinates,
            label: "Location found · retry address",
            message:
              "We have your GPS location, but couldn’t look up its postal code. Select the location above to try again.",
          });
        }
      },
      (error) =>
        update({
          status: "error",
          coordinates: null,
          label: null,
          message:
            error.code === 1
              ? "Location access is blocked. Allow it in your browser’s site settings, then try again. You can still enter your situation."
              : "We couldn’t get your location. Check your device’s location services and try again.",
        }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!manuallySelected.current) locate();
    }, 0);
    return () => {
      clearTimeout(timer);
      requestId.current += 1;
    };
  }, [locate]);
  const retry = () => {
    manuallySelected.current = false;
    setLocation({
      status: "locating",
      coordinates: null,
      label: null,
      message: "Looking for your current location…",
    });
    locate(location.coordinates ? location : undefined);
  };
  const selectAddress = (match: AddressMatch) => {
    manuallySelected.current = true;
    requestId.current += 1;
    setLocation({
      status: "ready",
      coordinates: match.coordinates,
      label: match.label || match.address,
      address: match.address,
      message: `Starting from ${match.address}. Resources currently cover Baltimore.`,
    });
  };
  return { location, retry, selectAddress };
}
