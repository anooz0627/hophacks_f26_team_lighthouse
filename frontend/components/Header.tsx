"use client";
import Link from "next/link";
import Icon from "./Icon";
export default function Header({ onOpenAdmin }: { onOpenAdmin: () => void }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="AidGraph home">
          <span className="brand-mark">
            <Icon name="route" size={24} />
          </span>
          Aid<span>Graph</span>
        </Link>
        <span className="region">
          <Icon name="pin" size={16} /> Baltimore, Maryland
        </span>
        <div className="header-actions">
          <button className="button button-quiet" onClick={onOpenAdmin}>
            <Icon name="settings" size={17} />
            <span>Availability</span>
          </button>
        </div>
      </div>
    </header>
  );
}
