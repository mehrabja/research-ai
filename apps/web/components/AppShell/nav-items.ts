import type { Route } from "next";

export type NavSection = "Overview" | "Research" | "Writing & AI" | "Review & publish" | "Workspace";
export type NavItem = { href: Route; icon: string; label: string; section: NavSection };

export const NAV_ITEMS: NavItem[] = [
  {section:"Overview", href:"/dashboard", icon:"⌂", label:"Dashboard"},
  {section:"Overview", href:"/workspace", icon:"◈", label:"Workspace"},
  {section:"Research", href:"/research", icon:"⌕", label:"Research discovery"},
  {section:"Research", href:"/sources", icon:"◎", label:"Sources"},
  {section:"Research", href:"/literature", icon:"▤", label:"Literature"},
  {section:"Research", href:"/evidence", icon:"◇", label:"Evidence"},
  {section:"Research", href:"/knowledge", icon:"✦", label:"Knowledge graph"},
  {section:"Research", href:"/research-canvas", icon:"⌘", label:"Research canvas"},
  {section:"Research", href:"/files", icon:"□", label:"Files & intelligence"},
  {section:"Research", href:"/pdf-workspace", icon:"▧", label:"PDF workspace"},
  {section:"Research", href:"/plan", icon:"☷", label:"Research plan"},
  {section:"Research", href:"/manuscript", icon:"▥", label:"Manuscript"},
  {section:"Writing & AI", href:"/generate", icon:"✧", label:"AI Studio"},
  {section:"Writing & AI", href:"/humanize", icon:"≈", label:"Humanize"},
  {section:"Writing & AI", href:"/translate", icon:"⇄", label:"Translate"},
  {section:"Review & publish", href:"/final-review", icon:"✓", label:"Final review"},
  {section:"Review & publish", href:"/publication", icon:"⇥", label:"Publication & export"},
  {section:"Review & publish", href:"/collaboration", icon:"◌", label:"Collaboration"},
  {section:"Workspace", href:"/jobs", icon:"◷", label:"Jobs"},
  {section:"Workspace", href:"/team", icon:"♙", label:"Team"},
  {section:"Workspace", href:"/usage-billing", icon:"◫", label:"Usage & billing"},
  {section:"Workspace", href:"/settings", icon:"⚙", label:"Settings"},
];
