"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function EvidencePage() {
  const { workspaceId } = useWorkspace();
  const [reportId, setReportId] = useState("");

  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: () => api.reports(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (!reportId && reports.data?.[0]?.id) {
      setReportId(reports.data[0].id);
    }
  }, [reports.data, reportId]);

  const matrix = useQuery({
    queryKey: ["evidence-matrix", reportId],
    queryFn: () => api.evidenceMatrix(reportId),
    enabled: !!reportId,
    retry: false,
  });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  const rows =
    (matrix.data?.rows ?? []).map((row) => ({
      ...row,
      evidence: row.evidence ?? [],
      citations: row.citations ?? [],
    }));

  const claimsWithEvidence = rows.filter(
    (row) => row.evidence.length > 0,
  ).length;

  const claimsWithCitations = rows.filter(
    (row) => row.citations.length > 0,
  ).length;

  const claimsWithoutEvidence = rows.filter(
    (row) => row.evidence.length === 0,
  ).length;

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Claim provenance
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Evidence
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Claim-level evidence and citation relationships
          are read from the report evidence matrix.
        </p>
      </header>

      <section className="card p-5">
        <div className="muted text-sm">
          Report
        </div>

        <select
          className="input mt-2 min-w-80"
          value={reportId}
          onChange={(event) =>
            setReportId(event.target.value)
          }
        >
          {reports.data?.map((report) => (
            <option
              key={report.id}
              value={report.id}
            >
              {report.topic}
            </option>
          ))}
        </select>

        {matrix.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            Evidence matrix unavailable:{" "}
            {matrix.error.message}
          </div>
        )}
      </section>

      <div className="grid md:grid-cols-4 gap-4">
        <Metric
          label="Claims"
          value={rows.length}
        />

        <Metric
          label="With evidence"
          value={claimsWithEvidence}
        />

        <Metric
          label="With citations"
          value={claimsWithCitations}
        />

        <Metric
          label="No evidence"
          value={claimsWithoutEvidence}
        />
      </div>

      <section className="card overflow-hidden">
        <div
          className="px-5 py-4 border-b"
          style={{
            borderColor: "var(--line)",
          }}
        >
          <div className="font-semibold">
            Claim evidence matrix
          </div>

          {matrix.data && (
            <div className="muted text-xs mt-1">
              Citation run{" "}
              {matrix.data.citation_run_id}
            </div>
          )}
        </div>

        <div className="divide-y">
          {matrix.isPending && (
            <div className="p-6 muted">
              Loading evidence matrix…
            </div>
          )}

          {!matrix.isPending &&
            !rows.length &&
            !matrix.error && (
              <div className="p-8 muted text-sm">
                No evidence rows are available for
                this report yet.
              </div>
            )}

          {rows.map((row) => (
            <article
              key={row.claim.id}
              className="p-5"
            >
              <div className="flex flex-wrap justify-between gap-3">
                <div>
                  <div className="font-medium">
                    {row.claim.claim_text}
                  </div>

                  <div className="muted text-xs mt-2">
                    {row.claim.claim_type} ·{" "}
                    {row.claim.status}
                  </div>
                </div>

                <div className="flex gap-2 text-xs">
                  <span className="rounded-full border px-3 py-1">
                    {row.evidence.length} evidence
                  </span>

                  <span className="rounded-full border px-3 py-1">
                    {row.citations.length} citations
                  </span>
                </div>
              </div>

              <div className="grid lg:grid-cols-2 gap-5 mt-5">
                <div>
                  <h3 className="font-medium text-sm">
                    Evidence
                  </h3>

                  <div className="mt-3 space-y-2">
                    {row.evidence.map(
                      (evidence) => (
                        <div
                          key={evidence.id}
                          className="rounded-xl border p-3"
                          style={{
                            borderColor:
                              "var(--line)",
                          }}
                        >
                          <div className="text-sm">
                            {evidence.evidence_type}
                          </div>

                          <div className="muted text-xs mt-1">
                            Support:{" "}
                            {evidence.support_level} ·
                            relevance{" "}
                            {evidence.relevance_score.toFixed(
                              2,
                            )}
                          </div>

                          <div className="muted text-xs mt-1 break-all">
                            Evidence ID:{" "}
                            {evidence.evidence_id}
                          </div>

                          {evidence.source_id && (
                            <div className="muted text-xs mt-1 break-all">
                              Source:{" "}
                              {evidence.source_id}
                            </div>
                          )}
                        </div>
                      ),
                    )}

                    {!row.evidence.length && (
                      <div className="muted text-sm">
                        No evidence linked to this
                        claim.
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium text-sm">
                    Citations
                  </h3>

                  <div className="mt-3 space-y-2">
                    {row.citations.map(
                      (citation) => (
                        <div
                          key={citation.id}
                          className="rounded-xl border p-3"
                          style={{
                            borderColor:
                              "var(--line)",
                          }}
                        >
                          <div className="text-sm">
                            {citation.relation_type}
                          </div>

                          <div className="muted text-xs mt-1">
                            Support:{" "}
                            {citation.support_level} ·
                            relevance{" "}
                            {citation.relevance_score.toFixed(
                              2,
                            )}
                          </div>

                          <div className="muted text-xs mt-1 break-all">
                            Citation ID:{" "}
                            {citation.citation_id}
                          </div>

                          {citation.paragraph_index !=
                            null && (
                            <div className="muted text-xs mt-1">
                              Paragraph{" "}
                              {
                                citation.paragraph_index
                              }
                              {citation.sentence_index !=
                              null
                                ? " · sentence " +
                                  citation.sentence_index
                                : ""}
                            </div>
                          )}
                        </div>
                      ),
                    )}

                    {!row.citations.length && (
                      <div className="muted text-sm">
                        No citation linked to this
                        claim.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="card p-5">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-2xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}