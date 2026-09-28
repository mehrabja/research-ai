"use client";

import { useState } from "react";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const [query, setQuery] = useState("");

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="btn ghost mobile-menu"
          type="button"
          aria-label="Open navigation"
          onClick={onMenuClick}
        >
          ☰
        </button>
        <input
          className="search"
          placeholder="Search papers, projects, evidence…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="tag">⌘ K</span>
      </div>
      <div className="topbar-right">
        <span className="tag success">API healthy</span>
        <button className="btn ghost" type="button" data-toast="No unread notifications">
          🔔
        </button>
        <div className="avatar">NI</div>
      </div>
    </header>
  );
}
