"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getReport } from "@/lib/api/reports";
import {
  enqueuePostTranslationHumanization,
  getCurrentPostTranslationHumanization,
} from "@/lib/api/postTranslationHumanization";
import { getCurrentTranslation } from "@/lib/api/translation";

export default function PostTranslationHumanizationPanel({
  reportId,
}: {
  reportId?: string;
}) {
  const [started, setStarted] = useState(false);
  const queryClient = useQueryClient();

  const report = useQuery({
    queryKey: ["post-translation-report", reportId],
    queryFn: () => getReport(reportId!),
    enabled: Boolean(reportId),
    refetchInterval: started
      ? (query) =>
          query.state.data?.status === "post_translation_review"
            ? 3000
            : false
      : false,
    staleTime: 2_000,
  });

  const translation = useQuery({
    queryKey: ["translation-current", reportId],
    queryFn: () => getCurrentTranslation(reportId!),
    enabled: Boolean(reportId),
    staleTime: 5_000,
  });

  const humanization = useQuery({
    queryKey: ["post-translation-humanization-current", reportId],
    queryFn: () => getCurrentPostTranslationHumanization(reportId!),
    enabled: Boolean(reportId),
    staleTime: 5_000,
  });

  const enqueue = useMutation({
    mutationFn: () => {
      if (!translation.data) {
        throw new Error("A completed translation is required first.");
      }
      return enqueuePostTranslationHumanization(
        reportId!,
        translation.data.run_id,
        translation.data.translation_version_id,
      );
    },
    onSuccess: async (data) => {
      setStarted(true);
      await queryClient.invalidateQueries({
        queryKey: ["post-translation-humanization-current", reportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["post-translation-report", reportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["report", reportId],
      });
      if (data.status === "not_eligible") {
        setStarted(false);
      }
    },
  });

  if (!reportId) return null;

  const firstError =
    report.error ?? translation.error ?? humanization.error ?? enqueue.error;
  if (firstError instanceof Error) {
    return (
      <section className="card pad" role="alert">
        <h3>Post-translation humanization unavailable</h3>
        <p className="muted" style={{ marginTop: 6 }}>
          {firstError.message}
        </p>
      </section>
    );
  }

  const status = report.data?.status;
  const run = humanization.data?.run;
  const canStart =
    status === "post_translation_review" &&
    Boolean(translation.data) &&
    !run &&
    !started &&
    !enqueue.isPending;

  return (
    <section className="card pad">
      <div className="row">
        <div>
          <div className="eyebrow">M17 · L4</div>
          <h3 style={{ marginTop: 4 }}>Post-translation humanization</h3>
          <p className="muted small" style={{ marginTop: 5 }}>
            Naturalize the translated output without re-translating it. The
            backend preserves protected terminology, identifiers and evidence
            markers and advances the report after a successful run.
          </p>
        </div>
        {status === "review_2" ? (
          <Link className="btn primary" href="/final-review">
            Open final review
          </Link>
        ) : (
          <button
            type="button"
            className="btn primary"
            disabled={!canStart}
            onClick={() => enqueue.mutate()}
          >
            {enqueue.isPending
              ? "Starting…"
              : started
                ? "Humanization queued"
                : status === "post_translation_review"
                  ? "Run humanization"
                  : "Waiting"}
          </button>
        )}
      </div>

      <div className="grid grid-3" style={{ marginTop: 14 }}>
        <div className="card metric">
          <div className="label">Pipeline status</div>
          <div className="value" style={{ fontSize: 20 }}>
            {status ?? "loading"}
          </div>
          <div className="delta">Backend report state</div>
        </div>
        <div className="card metric">
          <div className="label">Translation</div>
          <div className="value" style={{ fontSize: 20 }}>
            {translation.data ? "Available" : "Waiting"}
          </div>
          <div className="delta">
            {translation.data?.preservation_check_status ?? "Not completed"}
          </div>
        </div>
        <div className="card metric">
          <div className="label">Humanization run</div>
          <div className="value" style={{ fontSize: 20 }}>
            {run?.status ?? "Not started"}
          </div>
          <div className="delta">
            {run?.gate ?? "Awaiting M17 execution"}
          </div>
        </div>
      </div>

      {status === "translating" && (
        <p className="muted small" style={{ marginTop: 12 }}>
          Translation is still running. Humanization becomes available after
          the translation job completes.
        </p>
      )}

      {status === "post_translation_review" && !translation.data && (
        <p className="muted small" style={{ marginTop: 12 }}>
          The report reached post-translation review, but no completed
          translation output is visible yet. The panel will refresh while the
          pipeline settles.
        </p>
      )}

      {status === "post_translation_review" && translation.data && !run && (
        <p className="muted small" style={{ marginTop: 12 }}>
          Translation output v{translation.data.translation_version_id.slice(0, 8)}
          … is ready for post-translation humanization.
        </p>
      )}

      {status === "converging" && (
        <p className="muted small" style={{ marginTop: 12 }}>
          Post-translation humanization completed. The backend is advancing
          through convergence before the final review gate.
        </p>
      )}

      {status === "review_2" && (
        <p className="muted small" style={{ marginTop: 12 }}>
          Final review is now the active gate. Review the final language output
          before validation.
        </p>
      )}
    </section>
  );
}
