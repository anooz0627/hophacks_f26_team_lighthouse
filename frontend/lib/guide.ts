export type GuidePose =
  "rest" | "listen" | "search" | "review" | "guide" | "pause" | "done";
export function guidePose(state: string, reviewing = false): GuidePose {
  if (reviewing) return "review";
  switch (state) {
    case "listening":
      return "listen";
    case "understanding":
    case "building":
    case "replanning":
      return "search";
    case "ready":
      return "guide";
    case "completed":
      return "done";
    case "warning":
    case "no-plan":
      return "pause";
    default:
      return "rest";
  }
}
