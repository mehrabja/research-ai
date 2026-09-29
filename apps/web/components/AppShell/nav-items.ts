import type { Route } from "next";
export type NavItem = {
  href: Route;
  icon: string;
  label: string;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", icon: "⌂", label: "Dashboard" },
  { href: "/workspace", icon: "◈", label: "Workspace" },
  { href: "/research", icon: "⌕", label: "Research discovery" },
  { href: "/sources", icon: "◎", label: "Sources" },
  { href: "/literature", icon: "▤", label: "Literature" },
  { href: "/evidence", icon: "◇", label: "Evidence" },
  { href: "/knowledge", icon: "✦", label: "Knowledge graph" },
  { href: "/files", icon: "□", label: "Files & intelligence" },
  { href: "/plan", icon: "☷", label: "Research plan" },
  { href: "/manuscript", icon: "▥", label: "Manuscript" },
  { href: "/generate", icon: "✧", label: "AI Studio" },
  { href: "/humanize", icon: "≈", label: "Humanize" },
  { href: "/translate", icon: "⇄", label: "Translate" },
  { href: "/final-review", icon: "✓", label: "Final review" },
  { href: "/publication", icon: "⇥", label: "Publication & export" },
  { href: "/collaboration", icon: "◌", label: "Collaboration" },
  { href: "/jobs", icon: "◷", label: "Jobs" },
  { href: "/team", icon: "♙", label: "Team" },
  { href: "/usage-billing", icon: "◫", label: "Usage & billing" },
  { href: "/settings", icon: "⚙", label: "Settings" },
];
