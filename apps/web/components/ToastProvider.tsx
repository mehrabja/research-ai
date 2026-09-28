"use client";

import { useEffect, useRef, useState } from "react";

type ToastItem = { id: number; message: string };

/**
 * Ports assets/app.js's global `[data-toast]` click delegation into React.
 * Any element in the tree can keep using `data-toast="Message"` exactly as
 * the original static prototype did (buttons that don't yet call a real
 * mutation, demo-only actions, etc.) and it will surface a toast here.
 */
export function ToastProvider() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement | null;
      const trigger = target?.closest<HTMLElement>("[data-toast]");
      if (!trigger) return;
      const message = trigger.dataset.toast;
      if (!message) return;
      e.preventDefault();
      const id = ++idRef.current;
      setToasts((prev) => [...prev, { id, message }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 2200);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        right: 20,
        bottom: 20,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 50,
      }}
    >
      {toasts.map((t) => (
        <div className="toast" key={t.id} style={{ position: "static" }}>
          {t.message}
        </div>
      ))}
    </div>
  );
}
