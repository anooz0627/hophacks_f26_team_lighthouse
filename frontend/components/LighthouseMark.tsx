export default function LighthouseMark() {
  return (
    <svg className="lighthouse-mark" viewBox="0 0 40 40" width="40" height="40" fill="none" aria-hidden="true">
      <path className="lighthouse-beam" d="M6 9 15 13 6 17M34 9 25 13 34 17" />
      <path d="m16 19-3 15h14l-3-15M14 19h12M16 14v5m8-5v5M16 11l4-5 4 5M11 34h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <rect className="lighthouse-light" x="16" y="11" width="8" height="4" rx="1" />
      <path d="M19 34v-6h2v6" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
