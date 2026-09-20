import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import SpeechInput from "@/components/SpeechInput";
import { transcribeAudio } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  transcribeAudio: vi.fn(),
  errorMessage: (error: Error) => error.message,
}));
let stopTrack: ReturnType<typeof vi.fn>;
let media: MediaStream;

class Recorder {
  static isTypeSupported(type: string) {
    return type === "audio/webm;codecs=opus";
  }
  state = "inactive";
  mimeType = "audio/webm;codecs=opus";
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

beforeEach(() => {
  vi.clearAllMocks();
  stopTrack = vi.fn();
  media = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue(media) },
  });
  vi.stubGlobal("MediaRecorder", Recorder);
  vi.mocked(transcribeAudio).mockResolvedValue("I need food.");
});
afterEach(() => vi.unstubAllGlobals());

it("stops the microphone and returns editable text without submitting a plan", async () => {
  const onTranscript = vi.fn();
  const onBusyChange = vi.fn();
  render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={onTranscript}
      onBusyChange={onBusyChange}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Stop recording" }),
  );
  await waitFor(() =>
    expect(onTranscript).toHaveBeenCalledWith("I need food."),
  );
  expect(stopTrack).toHaveBeenCalledTimes(1);
  expect(transcribeAudio).toHaveBeenCalledTimes(1);
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
});

it("cancel discards a recording and releases the microphone without uploading", async () => {
  const onTranscript = vi.fn();
  render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={onTranscript}
      onBusyChange={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  await screen.findByRole("button", { name: "Stop recording" });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await screen.findByRole("button", { name: "Speak instead" });
  expect(stopTrack).toHaveBeenCalledTimes(1);
  expect(transcribeAudio).not.toHaveBeenCalled();
  expect(onTranscript).not.toHaveBeenCalled();
});

it("ignores a transcript that arrives after cancellation", async () => {
  let resolve!: (text: string) => void;
  vi.mocked(transcribeAudio).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const onTranscript = vi.fn();
  render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={onTranscript}
      onBusyChange={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Stop recording" }),
  );
  await screen.findByText("Turning your words into text…");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await act(async () => {
    resolve("Stale transcript");
  });
  expect(vi.mocked(transcribeAudio).mock.calls[0][1].aborted).toBe(true);
  expect(onTranscript).not.toHaveBeenCalled();
});

it("releases permission granted after cancellation", async () => {
  let resolve!: (stream: MediaStream) => void;
  vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={vi.fn()}
      onBusyChange={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await act(async () => {
    resolve(media);
  });
  expect(stopTrack).toHaveBeenCalledTimes(1);
  expect(transcribeAudio).not.toHaveBeenCalled();
});

it("unmount cancels recording and releases the microphone", async () => {
  const view = render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={vi.fn()}
      onBusyChange={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  await screen.findByRole("button", { name: "Stop recording" });
  view.unmount();
  expect(stopTrack).toHaveBeenCalledTimes(1);
  expect(transcribeAudio).not.toHaveBeenCalled();
});

it("denied microphone permission leaves typing available", async () => {
  const onBusyChange = vi.fn();
  vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(
    new DOMException("Denied", "NotAllowedError"),
  );
  render(
    <SpeechInput
      disabled={false}
      available
      onTranscript={vi.fn()}
      onBusyChange={onBusyChange}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Speak instead" }));
  await screen.findByText(/Microphone access is blocked/);
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
  expect(transcribeAudio).not.toHaveBeenCalled();
});
