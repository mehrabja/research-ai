"use client";

import Link from "next/link";
import { use, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export default function ReportPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = use(params);
  const queryClient = useQueryClient();

  const report = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => api.report(reportId),
  });

  const sources = useQuery({
    queryKey: ["sources", reportId],
    queryFn: () => api.sources(reportId),
  });

  const manuscript = useQuery({
    queryKey: ["manuscript", reportId],
    queryFn: () => api.manuscript(reportId),
    retry: false,
  });

  const citations = useQuery({
    queryKey: ["citations", reportId],
    queryFn: () => api.citations(reportId),
    retry: false,
  });

  const qa = useQuery({
    queryKey: ["qa", reportId],
    queryFn: () => api.qa(reportId),
    retry: false,
  });

  const [query, setQuery] = useState("");

  const search = useMutation({
    mutationFn: () => api.searchSources(reportId, query),
  });

  const add = useMutation({
    mutationFn: (
      candidate: Parameters<typeof api.createSource>[1],
    ) => api.createSource(reportId, candidate),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["sources", reportId],
      });
    },
  });

  if (report.isPending) {
    return (
      <div className="card p-6 muted">
        Loading report…
      </div>
    );
  }

  if (report.error) {
    return (
      <div
        className="card p-6"
        style={{ color: "var(--danger)" }}
      >
        Report unavailable: {report.error.message}
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <header>
        <Link
          href="/projects"
          className="muted text-sm"
        >
          ← Projects
        </Link>

        <div className="kicker mt-5">
          Report
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          {report.data.topic}
        </h1>

        <p className="muted mt-2">
          {report.data.domain || "No domain"} ·{" "}
          {report.data.output_language} ·{" "}
          {report.data.status}
        </p>
      </header>

      <div className="grid lg:grid-cols-3 gap-4">
        <Status
          title="Manuscript"
          value={
            manuscript.data
              ? "v" + manuscript.data.version.version
              : manuscript.isError
                ? "Not generated"
                : "Loading…"
          }
          description={
            manuscript.data?.version.title || ""
          }
        />

        <Status
          title="Citations"
          value={
            citations.data
              ? citations.data.run.citation_count +
                " / " +
                citations.data.run.claim_count
              : citations.isError
                ? "Not generated"
                : "Loading…"
          }
          description={
            citations.data
              ? "coverage " +
                (
                  citations.data.run.coverage_score *
                  100
                ).toFixed(1) +
                "%"
              : ""
          }
        />

        <Status
          title="Academic QA"
          value={
            qa.data?.run.status ||
            "Not generated"
          }
          description={
            qa.data
              ? qa.data.run.finding_count +
                " findings · " +
                qa.data.run.blocking_count +
                " blocking"
              : ""
          }
        />
      </div>

      <section className="card p-5">
        <h2 className="font-semibold">
          Evidence sources
        </h2>

        <p className="muted text-sm mt-1">
          Search the configured source provider and
          register candidates for this report.
        </p>

        <div className="mt-4 flex gap-2">
          <input
            className="input"
            placeholder="Search sources…"
            value={query}
            onChange={(event) =>
              setQuery(event.target.value)
            }
          />

          <button
            className="btn btn-primary"
            disabled={!query || search.isPending}
            onClick={() => search.mutate()}
          >
            {search.isPending
              ? "Searching…"
              : "Search"}
          </button>
        </div>

        {search.error && (
          <div
            className="text-sm mt-3"
            style={{ color: "var(--danger)" }}
          >
            {search.error.message}
          </div>
        )}

        <div className="mt-5 space-y-3">
          {(search.data?.candidates ?? []).map(
            (candidate, index) => (
              <div
                key={
                  candidate.external_source_id +
                  index
                }
                className="rounded-xl border p-4"
                style={{
                  borderColor: "var(--line)",
                }}
              >
                <div className="flex justify-between gap-4">
                  <div>
                    <div className="font-medium">
                      {candidate.title}
                    </div>

                    <div className="muted text-sm mt-1">
                      {candidate.authors
                        ?.slice(0, 3)
                        .join(", ") ||
                        "Authors unavailable"}

                      {candidate.year
                        ? " · " + candidate.year
                        : ""}
                    </div>
                  </div>

                  <button
                    className="btn btn-secondary text-sm"
                    disabled={add.isPending}
                    onClick={() =>
                      add.mutate(candidate)
                    }
                  >
                    Add
                  </button>
                </div>

                {candidate.abstract && (
                  <p className="muted text-sm mt-3 line-clamp-3">
                    {candidate.abstract}
                  </p>
                )}
              </div>
            ),
          )}
        </div>

        <div
          className="mt-6 border-t pt-5"
          style={{ borderColor: "var(--line)" }}
        >
          <h3 className="font-medium">
            Registered
          </h3>

          <div className="mt-3 space-y-2">
            {(sources.data?.items ?? []).map(
              (source) => (
                <div
                  key={source.id}
                  className="text-sm flex justify-between"
                >
                  <span>{source.title}</span>
                  <span className="muted">
                    {source.status}
                  </span>
                </div>
              ),
            )}

            {!sources.isPending &&
              sources.data?.items.length === 0 && (
                <div className="muted text-sm">
                  No registered sources yet.
                </div>
              )}
          </div>
        </div>
      </section>

      {manuscript.data && (
        <section className="card p-5">
          <h2 className="font-semibold">
            Manuscript architecture
          </h2>

          <div className="grid md:grid-cols-2 gap-3 mt-4">
            {manuscript.data.sections.map(
              (section) => (
                <div
                  key={section.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor: "var(--line)",
                  }}
                >
                  <div className="font-medium">
                    {section.title}
                  </div>

                  <div className="muted text-sm mt-1">
                    {section.section_type} ·{" "}
                    {section.word_budget} words
                  </div>

                  <div className="muted text-xs mt-2">
                    {section.citation_required
                      ? "Citation required"
                      : "Citation optional"}
                  </div>
                </div>
              ),
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function Status({
  title,
  value,
  description,
}: {
  title: string;
  value: string;
  description: string;
}) {
  return (
    <div className="card p-5">
      <div className="muted text-sm">
        {title}
      </div>

      <div className="text-xl font-semibold mt-2">
        {value}
      </div>

      <div className="muted text-sm mt-1">
        {description}
      </div>
    </div>
  );
}