"use client";
import { useEffect, useRef, useState } from "react";
import { errorMessage, transcribeAudio } from "@/lib/api";
import Icon from "./Icon";
import { Spinner } from "./ui";

type State = "idle" | "requesting" | "recording" | "transcribing";

export default function SpeechInput({
  disabled,
  available,
  onTranscript,
  onBusyChange,
}: {
  disabled: boolean;
  available: boolean;
  onTranscript: (text: string) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const request = useRef<AbortController | null>(null);
  const session = useRef(0);
  const callbacks = useRef({ onTranscript, onBusyChange });
  useEffect(() => {
    callbacks.current = { onTranscript, onBusyChange };
  }, [onTranscript, onBusyChange]);

  const release = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  };
  useEffect(
    () => () => {
      session.current += 1;
      request.current?.abort();
      release();
      callbacks.current.onBusyChange(false);
    },
    [],
  );

  const cancel = () => {
    session.current += 1;
    request.current?.abort();
    release();
    setState("idle");
    callbacks.current.onBusyChange(false);
  };
  const start = async () => {
    if (state !== "idle" || disabled) return;
    setError(null);
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "Voice input isn’t supported in this browser. You can type below or try another browser.",
      );
      return;
    }
    const id = ++session.current;
    setState("requesting");
    callbacks.current.onBusyChange(true);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (id !== session.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/ogg;codecs=opus",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const recording = new MediaRecorder(
        media,
        mimeType ? { mimeType } : undefined,
      );
      recorder.current = recording;
      const chunks: Blob[] = [];
      let size = 0;
      recording.ondataavailable = ({ data }) => {
        if (id !== session.current) return;
        size += data.size;
        if (size > 10 * 1024 * 1024) {
          cancel();
          setError(
            "The recording is too large. Please try a shorter recording.",
          );
        } else if (data.size) chunks.push(data);
      };
      recording.onerror = () => {
        if (id !== session.current) return;
        cancel();
        setError(
          "Recording stopped unexpectedly. Please try again or type your situation.",
        );
      };
      recording.onstop = async () => {
        if (id !== session.current) return;
        release();
        setState("transcribing");
        const controller = new AbortController();
        request.current = controller;
        try {
          const transcript = await transcribeAudio(
            new Blob(chunks, {
              type: recording.mimeType || mimeType || "audio/webm",
            }),
            controller.signal,
          );
          if (id !== session.current) return;
          if (!transcript.trim())
            throw new Error("No speech was recognized. Please try again.");
          callbacks.current.onTranscript(transcript);
        } catch (err) {
          if (id === session.current) setError(errorMessage(err));
        } finally {
          if (id === session.current) {
            setState("idle");
            callbacks.current.onBusyChange(false);
          }
        }
      };
      recording.start(1000);
      setSeconds(0);
      setState("recording");
      const started = Date.now();
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        setSeconds(elapsed);
        if (elapsed >= 60) release();
      }, 1000);
    } catch (err) {
      if (id !== session.current) return;
      release();
      setState("idle");
      callbacks.current.onBusyChange(false);
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access is blocked. Allow it in your browser’s site settings or type below."
          : "We couldn’t start the microphone. Check your device and try again.",
      );
    }
  };
  return (
    <div className="speech-input">
      <div className="speech-actions">
        {state === "idle" ? (
          <button
            type="button"
            className="button button-small"
            disabled={disabled || !available}
            onClick={() => void start()}
            aria-describedby="speech-help"
          >
            <Icon name="mic" size={18} /> Speak instead
          </button>
        ) : (
          <>
            {state === "recording" ? (
              <button
                type="button"
                className="button button-small"
                onClick={release}
              >
                Stop recording
              </button>
            ) : (
              <Spinner />
            )}
            <button type="button" className="text-button" onClick={cancel}>
              Cancel
            </button>
          </>
        )}
        <span role="status" className="small">
          {state === "requesting"
            ? "Allow microphone access to begin."
            : state === "recording"
              ? "Recording…"
              : state === "transcribing"
                ? "Turning your words into text…"
                : ""}
        </span>
        {state === "recording" && (
          <span className="small" aria-hidden="true">
            {seconds}s / 60s
          </span>
        )}
      </div>
      <p id="speech-help" className="field-hint">
        {available
          ? "Audio is sent to ElevenLabs to add text below. You can edit it before continuing."
          : "Voice input is unavailable right now. You can still type below."}
      </p>
      {error && (
        <p className="alert error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
