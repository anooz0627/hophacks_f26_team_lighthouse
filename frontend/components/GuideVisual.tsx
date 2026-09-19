"use client";
import Image from "next/image";
import { guidePose } from "@/lib/guide";
const artwork = {
  rest: "/guide/rest-cutout.png",
  review: "/guide/review-cutout.png",
  guide: "/guide/guide-cutout.png",
};
export default function GuideVisual({
  state,
  still,
  reviewing = false,
}: {
  state: string;
  still: boolean;
  reviewing?: boolean;
}) {
  const pose = guidePose(state, reviewing);
  const frameName =
    pose === "review" || pose === "search"
      ? "review"
      : pose === "guide" || pose === "done"
        ? "guide"
        : "rest";
  return (
    <div
      className="guide-visual-canvas guide-art"
      data-pose={pose}
      data-motion={still ? "static" : "transitions"}
      data-artwork={frameName}
    >
      <div className="guide-art-frame" key={frameName}>
        <Image
          src={artwork[frameName]}
          width={1024}
          height={1024}
          sizes="(max-width: 640px) 112px, 176px"
          className="guide-character"
          loading="eager"
          alt=""
          draggable={false}
        />
      </div>
    </div>
  );
}
