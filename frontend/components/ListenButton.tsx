"use client";
import { useEffect, useRef, useState } from "react";
import { planAudioUrl } from "@/lib/api";
import Icon from "./Icon";
import { Spinner } from "./ui";

type State = "idle" | "loading" | "playing" | "paused" | "error";

export default function ListenButton({ planId }: { planId: string }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<State>("idle");

  useEffect(
    () => () => {
      audio.current?.pause();
    },
    [],
  );

  const toggle = () => {
    if (state === "playing") {
      audio.current?.pause();
      setState("paused");
      return;
    }
    if (state === "paused" && audio.current) {
      void audio.current.play();
      setState("playing");
      return;
    }
    const el = new Audio(planAudioUrl(planId));
    el.preload = "auto";
    el.onplaying = () => setState("playing");
    el.onended = () => setState("idle");
    el.onerror = () => setState("error");
    audio.current = el;
    setState("loading");
    el.play().catch(() => setState("error"));
  };

  const label =
    state === "loading"
      ? "Preparing audio…"
      : state === "playing"
        ? "Pause"
        : state === "paused"
          ? "Resume"
          : "Listen to this plan";

  return (
    <div className="listen-row">
      <button
        type="button"
        className="button button-small"
        onClick={toggle}
        disabled={state === "loading"}
        aria-pressed={state === "playing"}
      >
        {state === "loading" ? <Spinner /> : <Icon name="speaker" size={16} />}
        {label}
      </button>
      <span className="muted small">
        {state === "error"
          ? "Audio is unavailable right now. The written steps above are complete."
          : "Hear every step read aloud, with times and what to bring."}
      </span>
    </div>
  );
}
