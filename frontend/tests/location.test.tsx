import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import useCurrentLocation from "@/lib/useCurrentLocation";
import { getLocationLabel } from "@/lib/api";

vi.mock("@/lib/api", () => ({ getLocationLabel: vi.fn() }));
const coordinates = { latitude: 39.329, longitude: -76.615 };

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success) => success({ coords: coordinates })),
    },
  });
});

it("uses the postal label while keeping exact GPS coordinates for routes", async () => {
  vi.mocked(getLocationLabel).mockResolvedValue({ label: "21218, Baltimore" });
  const { result } = renderHook(useCurrentLocation);
  await waitFor(() =>
    expect(result.current.location.label).toBe("21218, Baltimore"),
  );
  expect(result.current.location.coordinates).toEqual({
    lat: 39.329,
    lng: -76.615,
  });
});

it("keeps GPS usable and offers a retry when postal lookup fails", async () => {
  vi.mocked(getLocationLabel).mockRejectedValue(new Error("Offline"));
  const { result } = renderHook(useCurrentLocation);
  await waitFor(() =>
    expect(result.current.location.message).toContain("couldn’t look up"),
  );
  expect(result.current.location.status).toBe("ready");
  expect(result.current.location.coordinates).not.toBeNull();
});

it("does not assign a Baltimore address outside its coverage", async () => {
  vi.mocked(getLocationLabel).mockResolvedValue({ label: null });
  const { result } = renderHook(useCurrentLocation);
  await waitFor(() =>
    expect(result.current.location.label).toBe("Outside Baltimore"),
  );
});

it("ignores an old postal response after location is retried", async () => {
  let resolveOld!: (value: { label: string }) => void;
  vi.mocked(getLocationLabel)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockResolvedValue({ label: "21201, Baltimore" });
  const { result } = renderHook(useCurrentLocation);
  await waitFor(() => expect(getLocationLabel).toHaveBeenCalledTimes(1));
  act(() => result.current.retry());
  await waitFor(() =>
    expect(result.current.location.label).toBe("21201, Baltimore"),
  );
  await act(async () => resolveOld({ label: "21218, Baltimore" }));
  expect(result.current.location.label).toBe("21201, Baltimore");
});

it("a late GPS response cannot overwrite a selected address", async () => {
  let resolveGps!: PositionCallback;
  vi.mocked(navigator.geolocation.getCurrentPosition).mockImplementation(
    (success) => {
      resolveGps = success;
    },
  );
  const { result } = renderHook(useCurrentLocation);
  await waitFor(() =>
    expect(navigator.geolocation.getCurrentPosition).toHaveBeenCalledTimes(1),
  );
  const match = {
    address: "400 W Lexington St, Baltimore, MD",
    label: "21201, Baltimore",
    coordinates: { lat: 39.29129, lng: -76.62235 },
  };
  act(() => result.current.selectAddress(match));
  await act(async () =>
    resolveGps({ coords: coordinates } as GeolocationPosition),
  );
  expect(result.current.location.coordinates).toEqual(match.coordinates);
  expect(result.current.location.address).toBe(match.address);
  expect(getLocationLabel).not.toHaveBeenCalled();
});
