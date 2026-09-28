"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "@/styles/boot.module.css";

type Phase = [title: string, status: string, heading: string, sub: string];

const PHASES: Phase[] = [
  [
    "Initializing workspace",
    "Secure workspace handshake",
    "Preparing your research workspace",
    "Synchronizing workspace context and preparing the tools you need for evidence-grounded research.",
  ],
  [
    "Loading source context",
    "Connecting source indexes",
    "Loading research context",
    "Bringing projects, source collections, files and recent research activity into one workspace.",
  ],
  [
    "Building evidence layer",
    "Preparing evidence graph",
    "Assembling the evidence layer",
    "Organizing claims, citations and supporting passages so every insight stays traceable.",
  ],
  [
    "Composing workspace graph",
    "Mapping research relationships",
    "Mapping your research",
    "Connecting literature, evidence, concepts and manuscript context into a coherent research graph.",
  ],
  [
    "Workspace ready",
    "Everything is ready",
    "Ready to research",
    "Your research environment is prepared. Opening your workspace now.",
  ],
];

const STEP_LABELS = ["Workspace", "Sources", "Evidence", "Research graph", "Ready"];
const DURATION_MS = 4400;
const REDIRECT_TARGET = "/dashboard";

export default function BootPage() {
  const router = useRouter();
  const [progress, setProgress] = useState(0);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    let frame: number;
    let redirectTimer: ReturnType<typeof setTimeout>;

    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now;
      const x = Math.min((now - startRef.current) / DURATION_MS, 1);
      const n = Math.min(4, Math.floor(x * 5));
      setProgress(x);
      setPhaseIndex(n);
      if (x < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        redirectTimer = setTimeout(() => router.push(REDIRECT_TARGET), 700);
      }
    };
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(redirectTimer);
    };
  }, [router]);

  const phase: Phase =
    PHASES[phaseIndex] ?? PHASES[PHASES.length - 1]!;

  const [phaseLabel, statusLabel, heading, sub] = phase;
  const pct = Math.floor(progress * 100);

  return (
    <div className={styles.wrapper}>
      <main className={styles.loader}>
        <div className={styles.halo} aria-hidden="true" />
        <div className={`${styles.halo} ${styles.h2}`} aria-hidden="true" />
        <div className={styles.floaters} aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <section className={styles.shell} aria-live="polite">
          <div className={styles.brand}>
            <div className={styles.mark}>R</div>
            <span>Research AI</span>
          </div>
          <div className={styles.visual} aria-hidden="true">
            <div className={styles.beam} />
            <div className={`${styles.beam} ${styles.b2}`} />
            <div className={`${styles.beam} ${styles.b3}`} />
            <div className={styles.ring} />
            <div className={`${styles.ring} ${styles.r2}`} />
            <div className={`${styles.ring} ${styles.r3}`} />
            <div className={styles.core} />
          </div>
          <h1 className={styles.title}>{heading}</h1>
          <p className={styles.sub}>{sub}</p>
          <div className={styles.progress}>
            <div className={styles.bar}>
              <span style={{ width: `${pct}%` }} />
            </div>
            <div className={styles.meta}>
              <span>{phaseLabel}</span>
              <span>{pct}%</span>
            </div>
          </div>
          <div className={styles.status}>
            <i />
            <span>{statusLabel}</span>
          </div>
          <div className={styles.steps}>
            {STEP_LABELS.map((label, i) => (
              <span
                key={label}
                className={`${styles.step} ${i < phaseIndex ? styles.done : ""} ${
                  i === phaseIndex ? styles.on : ""
                }`}
              >
                <b />
                {label}
              </span>
            ))}
          </div>
          <div className={styles.foot}>Evidence-first research environment · Research AI</div>
        </section>
      </main>
    </div>
  );
}
