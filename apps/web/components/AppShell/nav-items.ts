import type { Route } from "next";
import { ROUTES } from "@/lib/routes";

export type NavSection = "Overview" | "Research" | "Writing & AI" | "Review & publish" | "Workspace";
export type NavItem = { href: Route; icon: string; label: string; section: NavSection };

export const NAV_ITEMS: NavItem[] = [
  {section:"Overview", href:ROUTES.dashboard, icon:"⌂", label:"Dashboard"},
  {section:"Overview", href:ROUTES.workspace, icon:"◈", label:"Workspace"},
  {section:"Overview", href:ROUTES.search, icon:"⌕", label:"Global search"},
  {section:"Research", href:ROUTES.research, icon:"⌕", label:"Research discovery"},
  {section:"Research", href:ROUTES.sources, icon:"◎", label:"Sources"},
  {section:"Research", href:ROUTES.literature, icon:"▤", label:"Literature"},
  {section:"Research", href:ROUTES.evidence, icon:"◇", label:"Evidence"},
  {section:"Research", href:ROUTES.knowledge, icon:"✦", label:"Knowledge graph"},
  {section:"Research", href:ROUTES.researchCanvas, icon:"⌘", label:"Research canvas"},
  {section:"Research", href:ROUTES.files, icon:"□", label:"Files & intelligence"},
  {section:"Research", href:ROUTES.pdfWorkspace, icon:"▧", label:"PDF workspace"},
  {section:"Research", href:ROUTES.plan, icon:"☷", label:"Research plan"},
  {section:"Research", href:ROUTES.manuscript, icon:"▥", label:"Manuscript"},
  {section:"Writing & AI", href:ROUTES.aiStudio, icon:"✧", label:"AI Studio"},
  {section:"Writing & AI", href:ROUTES.humanize, icon:"≈", label:"Humanize"},
  {section:"Writing & AI", href:ROUTES.translate, icon:"⇄", label:"Translate"},
  {section:"Review & publish", href:ROUTES.finalReview, icon:"✓", label:"Final review"},
  {section:"Review & publish", href:ROUTES.publication, icon:"⇥", label:"Publication & export"},
  {section:"Review & publish", href:ROUTES.collaboration, icon:"◌", label:"Collaboration"},
  {section:"Workspace", href:ROUTES.jobs, icon:"◷", label:"Jobs"},
  {section:"Workspace", href:ROUTES.team, icon:"♙", label:"Team"},
  {section:"Workspace", href:ROUTES.usageBilling, icon:"◫", label:"Usage & billing"},
  {section:"Workspace", href:ROUTES.settings, icon:"⚙", label:"Settings"},
];
