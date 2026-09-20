import type { CSSProperties } from "react";
const paths = {
  arrow: "M5 12h14m-6-6 6 6-6 6",
  back: "M19 12H5m6-6-6 6 6 6",
  mic: "M9 5a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0V5ZM5 10v1a7 7 0 0 0 14 0v-1M12 18v4m-4 0h8",
  check: "m5 12 4 4L19 6",
  pin: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0ZM12 7v6m-3-3h6",
  home: "m3 10 9-7 9 7v10H3V10Zm6 10v-7h6v7",
  food: "M5 3v7m4-7v7M3 3v5a4 4 0 0 0 8 0V3M7 12v9M19 3c-4 3-4 10 0 10V3Zm0 10v8",
  bus: "M5 16h14V4H5v12Zm0-6h14M7 16v4m10-4v4M8 13h.01M16 13h.01",
  support: "M12 3v18M3 12h18M6 6l12 12M18 6 6 18",
  phone: "M7 3H3c0 10 8 18 18 18v-4l-5-2-2 2a14 14 0 0 1-7-7l2-2-2-5Z",
  clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  edit: "m15 4 5 5M4 15 15 4a3.5 3.5 0 0 1 5 5L9 20l-6 1 1-6Z",
  close: "m6 6 12 12M18 6 6 18",
  external: "M14 3h7v7m0-7L10 14M10 5H4v15h15v-6",
  warning: "m12 3 10 18H2L12 3Zm0 6v5m0 3v.1",
  settings: "M4 7h16M4 17h16M8 4v6m8 4v6",
  chevron: "m6 9 6 6 6-6",
  route: "M6 5h10a4 4 0 0 1 0 8H8a4 4 0 0 0 0 8h10M6 3v4m12 12v4",
  lighthouse: "M9.5 21h5M10 10.5h4l1 10.5H9l1-10.5ZM9 10.5h6M12 3.5l-2.5 3h5L12 3.5ZM9.5 6.5h5v4h-5v-4ZM3.5 6.5l3.5 1.2M3.5 11.5l3.5-1.2M20.5 6.5 17 7.7M20.5 11.5 17 10.3",
  speaker:
    "M11 5 6 9H2v6h4l5 4V5Zm4.5 3.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12",
  info: "M12 11v6m0-10v.1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
};
export type IconName = keyof typeof paths;
export default function Icon({
  name,
  size = 20,
  style,
}: {
  name: IconName;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
