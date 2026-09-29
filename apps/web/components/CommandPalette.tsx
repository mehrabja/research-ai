"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { NAV_ITEMS } from "@/components/AppShell/nav-items";
import { useResearchContext } from "@/lib/research-context";

type Command = {
  id: string;
  title: string;
  description: string;
  href: Route;
};

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] =
    useState(0);
  const inputRef =
    useRef<HTMLInputElement | null>(null);
  const router = useRouter();
  const {
    contextHref,
    project,
    report,
  } = useResearchContext();

  useEffect(() => {
    if (!open) return;

    const timer = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const base = NAV_ITEMS.map((item) => ({
      id: item.href,
      title: item.label,
      description: item.section,
      href: contextHref(item.href),
    }));

    const currentResearch: Command = {
      id: "current-research",
      title: project
        ? "Open " + project.name
        : "Open current project",
      description: "Current research context",
      href: contextHref("/research"),
    };

    const currentReport: Command[] = report
      ? [
          {
            id: "current-report",
            title: "Open current report",
            description: report.topic,
            href: contextHref("/manuscript"),
          },
        ]
      : [];

    return [
      currentResearch,
      ...currentReport,
      ...base,
    ];
  }, [
    contextHref,
    project,
    report,
  ]);

  const normalized = query.trim().toLowerCase();
  const filtered = normalized
    ? commands.filter((command) =>
        [command.title, command.description]
          .join(" ")
          .toLowerCase()
          .includes(normalized),
      )
    : commands;

  function onInputKeyDown(
    event: React.KeyboardEvent<HTMLInputElement>,
  ) {
    if (filtered.length === 0) {
      if (event.key === "Escape") onClose();
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex(
        (current) =>
          (current + 1) % filtered.length,
      );
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex(
        (current) =>
          (current - 1 + filtered.length) %
          filtered.length,
      );
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const command = filtered[Math.min(activeIndex, Math.max(filtered.length - 1, 0))];
      if (!command) return;
      router.push(command.href);
      onClose();
    }
  }

  if (!open) return null;

  const safeActiveIndex = Math.min(activeIndex, Math.max(filtered.length - 1, 0));
  const activeId = filtered[safeActiveIndex]
    ? `command-${filtered[activeIndex].id.replace(/[^a-zA-Z0-9_-]/g, "_")}`
    : undefined;

  return (
    <div className="command-overlay">
      <button
        className="command-backdrop"
        type="button"
        aria-label="Close command palette"
        onClick={onClose}
      />

      <section
        className="command-palette card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-palette-title"
      >
        <div className="command-head">
          <div>
            <div className="eyebrow">
              Quick navigation
            </div>
            <h2 id="command-palette-title">
              Command palette
            </h2>
          </div>

          <button
            className="btn ghost"
            type="button"
            onClick={onClose}
          >
            Esc
          </button>
        </div>

        <input
          ref={inputRef}
          className="input command-input"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={onInputKeyDown}
          placeholder="Search views and current research…"
          aria-label="Search commands"
          aria-controls="command-list"
          aria-activedescendant={activeId}
        />

        <div
          id="command-list"
          className="command-list"
          role="listbox"
          aria-label="Commands"
        >
          {filtered.map((command, index) => {
            const itemId = `command-${command.id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
            const active = index === safeActiveIndex;

            return (
              <Link
                key={command.id}
                id={itemId}
                href={command.href}
                className="command-item"
                aria-selected={active}
                role="option"
                onMouseEnter={() =>
                  setActiveIndex(index)
                }
                onClick={onClose}
                style={
                  active
                    ? {
                        background:
                          "var(--secondary)",
                      }
                    : undefined
                }
              >
                <span>
                  <strong>{command.title}</strong>
                  <span>
                    {command.description}
                  </span>
                </span>
                <span aria-hidden="true">
                  ↵
                </span>
              </Link>
            );
          })}

          {filtered.length === 0 && (
            <div className="empty command-empty">
              No matching commands.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
