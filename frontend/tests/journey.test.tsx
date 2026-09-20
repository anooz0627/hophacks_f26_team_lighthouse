import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import Home from "@/app/page";
import * as api from "@/lib/api";
import { emptyConstraints } from "@/lib/constraints";
import type { Plan, PlanBundle, UserConstraints } from "@/lib/types";

vi.mock("next/dynamic", () => ({ default: () => () => <div>Route map</div> }));
vi.mock("@/components/GuideVisual", () => ({ default: () => <div /> }));
vi.mock("@/lib/api", () => ({
  getResources: vi.fn(),
  getHealth: vi.fn(),
  getLocationLabel: vi.fn(),
  extract: vi.fn(),
  generatePlans: vi.fn(),
  setResourceStatus: vi.fn(),
  resetResources: vi.fn(),
  planAudioUrl: vi.fn(),
  transcribeAudio: vi.fn(),
  searchAddresses: vi.fn(),
  errorMessage: (error: Error) => error.message,
}));
let uc: UserConstraints;
const gps = { latitude: 39.3, longitude: -76.61 };

class Recorder {
  static isTypeSupported() {
    return true;
  }
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable?: (event: { data: Blob }) => void;
  onstop?: () => void;
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    queueMicrotask(() => {
      this.ondataavailable?.({
        data: new Blob(["audio"], { type: this.mimeType }),
      });
      this.onstop?.();
    });
  }
}
afterEach(() => vi.unstubAllGlobals());

function planFor(constraints: UserConstraints): PlanBundle {
  return {
    plans: [
      {
        plan_id: "test-plan",
        strategy: "recommended",
        constraints,
        now: "2026-09-20T12:01",
        created_at: "2026-09-20T12:01",
        steps: [],
        resource_ids: [],
        total_cost_usd: 0,
        total_travel_min: 0,
        score: 0,
        feasible: false,
        unmet_needs: ["food"],
        explanation: "No open service nearby",
        rejected: [],
        tradeoff: "",
        graph: { nodes: [], edges: [] },
      } satisfies Plan,
    ],
    diff: null,
    alternatives_note: "",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  uc = {
    ...emptyConstraints(),
    raw_text: "I need food",
    needs: [{ type: "food", priority: "high", deadline: "tonight" }],
  };
  uc.constraints.current_location = { lat: 39.291, lng: -76.6215 };
  vi.mocked(api.getResources).mockResolvedValue([]);
  vi.mocked(api.getLocationLabel).mockResolvedValue({
    label: "21218, Baltimore",
  });
  vi.mocked(api.getHealth).mockResolvedValue({
    ok: true,
    llm: false,
    voice: false,
    resources: 0,
  });
  vi.mocked(api.extract).mockResolvedValue(uc);
  vi.mocked(api.generatePlans).mockImplementation(async (constraints) =>
    planFor(constraints),
  );
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((success) => success({ coords: gps })),
    },
  });
});

async function review() {
  fireEvent.change(screen.getByLabelText("Describe your situation"), {
    target: { value: "I need food" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Review my details" }));
  await screen.findByText("Did we get this right?");
}

describe("planner journey", () => {
  it.each([null, 22])(
    "extracts the latest transcript after editing another detail, preserving only explicit age edits (%s)",
    async (manualAge) => {
      vi.mocked(api.getHealth).mockResolvedValue({
        ok: true,
        llm: false,
        voice: true,
        resources: 0,
      });
      vi.stubGlobal("MediaRecorder", Recorder);
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: {
          getUserMedia: vi
            .fn()
            .mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
        },
      });
      vi.mocked(api.transcribeAudio).mockResolvedValue(
        "I'm nineteen. I have ten dollars.",
      );
      render(<Home />);
      await screen.findByRole("button", { name: "21218, Baltimore" });
      await review();
      fireEvent.click(screen.getByRole("button", { name: "Edit" }));
      const dialog = screen.getByRole("dialog", { name: "Edit your details" });
      fireEvent.change(within(dialog).getByLabelText(/Gender \(optional\)/), {
        target: { value: "non_binary" },
      });
      if (manualAge !== null) {
        fireEvent.change(
          within(dialog).getByLabelText("Age", { exact: true }),
          { target: { value: String(manualAge) } },
        );
      }
      fireEvent.click(
        within(dialog).getByRole("button", { name: "Save details" }),
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Back to your situation" }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
      fireEvent.click(
        await screen.findByRole("button", { name: "Stop recording" }),
      );
      const fullText = "I need food I'm nineteen. I have ten dollars.";
      await waitFor(() =>
        expect(
          (
            screen.getByLabelText(
              "Describe your situation",
            ) as HTMLTextAreaElement
          ).value,
        ).toBe(fullText),
      );
      vi.mocked(api.extract).mockResolvedValue({
        ...uc,
        raw_text: fullText,
        constraints: { ...uc.constraints, age: 19, budget_usd: 10 },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Review my details" }),
      );
      await screen.findByText("Did we get this right?");
      expect(api.extract).toHaveBeenLastCalledWith(fullText);
      expect(
        screen.getByRole("button", {
          name: `Edit Age: ${manualAge ?? 19} years old`,
        }),
      ).toBeTruthy();
      expect(
        screen.getByRole("button", { name: "Edit Budget: $10" }),
      ).toBeTruthy();
      expect(
        screen.getByRole("button", { name: "Edit Gender: Non-binary" }),
      ).toBeTruthy();
    },
  );

  it("uses GPS, asks the server for current time, and preserves the plan when going back", async () => {
    render(<Home />);
    await screen.findByRole("button", {
      name: "21218, Baltimore",
    });
    await review();
    fireEvent.click(screen.getByRole("button", { name: "Find My Options" }));
    await screen.findByRole("button", { name: "Back to review your details" });
    expect(api.generatePlans).toHaveBeenCalledWith(
      expect.objectContaining({
        constraints: expect.objectContaining({
          current_location: { lat: 39.3, lng: -76.61 },
        }),
      }),
      undefined,
      undefined,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Back to review your details" }),
    );
    expect(
      screen.getByRole("button", { name: "Return to my plan" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Your situation$/ }));
    expect(
      (screen.getByLabelText("Describe your situation") as HTMLTextAreaElement)
        .value,
    ).toBe("I need food");
    fireEvent.click(screen.getByRole("button", { name: "Review my details" }));
    await screen.findByText("Did we get this right?");
    fireEvent.click(screen.getByRole("button", { name: "Return to my plan" }));
    await screen.findByRole("button", { name: "Back to review your details" });
    expect(api.extract).toHaveBeenCalledTimes(1);
    expect(api.generatePlans).toHaveBeenCalledTimes(1);
  });

  it("invalidates the old plan after a support or gender edit", async () => {
    render(<Home />);
    await screen.findByRole("button", {
      name: "21218, Baltimore",
    });
    await review();
    fireEvent.click(screen.getByRole("button", { name: "Find My Options" }));
    await screen.findByRole("button", { name: "Back to review your details" });
    fireEvent.click(screen.getByRole("button", { name: /Your situation$/ }));
    fireEvent.click(screen.getByText("Add details"));
    fireEvent.click(screen.getByLabelText(/I need shorter walks/));
    fireEvent.change(screen.getByLabelText(/Gender \(optional\)/), {
      target: { value: "non_binary" },
    });
    expect(
      (
        screen.getByRole("button", {
          name: /Your action plan$/,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Review my details" }));
    await screen.findByText("Did we get this right?");
    expect(screen.getByText("Non-binary")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Find My Options" }));
    await waitFor(() => expect(api.generatePlans).toHaveBeenCalledTimes(2));
    expect(
      vi.mocked(api.generatePlans).mock.calls[1][0].constraints,
    ).toMatchObject({
      gender: "non_binary",
      accessibility: ["limited_walking"],
    });
  });

  it("retains the situation when GPS is denied and never plans from a default neighborhood", async () => {
    vi.mocked(navigator.geolocation.getCurrentPosition).mockImplementation(
      (_success, failure) => failure?.({ code: 1 } as GeolocationPositionError),
    );
    render(<Home />);
    await screen.findByText(/Location access is blocked/);
    await review();
    expect(
      (
        screen.getByRole("button", {
          name: "Find My Options",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(api.generatePlans).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Back to your situation" }),
    );
    expect(
      (screen.getByLabelText("Describe your situation") as HTMLTextAreaElement)
        .value,
    ).toBe("I need food");
    vi.mocked(navigator.geolocation.getCurrentPosition).mockImplementation(
      (success) => success({ coords: gps } as GeolocationPosition),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry location" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Use my current location" }),
    );
    await screen.findByRole("button", {
      name: "21218, Baltimore",
    });
    expect(screen.queryByText("Starting neighborhood")).toBeNull();
    expect(screen.queryByText("Hide character")).toBeNull();
  });
});

it("lets a user with blocked GPS choose an address and uses that address in every new plan", async () => {
  vi.mocked(navigator.geolocation.getCurrentPosition).mockImplementation(
    (_success, failure) => failure?.({ code: 1 } as GeolocationPositionError),
  );
  const match = {
    address: "400 W LEXINGTON ST, BALTIMORE, MD, 21201",
    label: "21201, Baltimore",
    coordinates: { lat: 39.29129, lng: -76.62235 },
  };
  vi.mocked(api.searchAddresses).mockResolvedValue([match]);
  render(<Home />);
  await screen.findByText(/Location access is blocked/);
  await review();
  fireEvent.click(
    screen.getByRole("button", {
      name: "Edit Starting from: Location access needed",
    }),
  );
  fireEvent.change(screen.getByLabelText("Street address"), {
    target: { value: "400 W Lexington St Baltimore MD" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Find address" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Use this address" }),
  );
  expect(
    screen.getByRole("button", {
      name: `Edit Starting from: ${match.address}`,
    }),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Find My Options" }));
  await screen.findByRole("button", { name: "Back to review your details" });
  expect(
    vi.mocked(api.generatePlans).mock.calls[0][0].constraints.current_location,
  ).toEqual(match.coordinates);
  fireEvent.click(screen.getByRole("button", { name: "21201, Baltimore" }));
  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(
    screen.getByRole("button", { name: "Back to review your details" }),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "21201, Baltimore" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Use my current location" }),
  );
  await screen.findByText(/previous starting location is still selected/);
  expect(screen.getByRole("button", { name: "Find My Options" })).toBeTruthy();
  expect(
    (
      screen.getByRole("button", {
        name: /Your action plan$/,
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
