"use client";

import {
  useEffect,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function ManuscriptPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [reportId, setReportId] =
    useState("");

  const [selectedSectionKey, setSelectedSectionKey] =
    useState("");

  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: () =>
      api.reports(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (
      !reportId &&
      reports.data?.[0]?.id
    ) {
      setReportId(
        reports.data[0].id,
      );
    }
  }, [reports.data, reportId]);

  const manuscript = useQuery({
    queryKey: ["manuscript", reportId],
    queryFn: () =>
      api.manuscript(reportId),
    enabled: !!reportId,
    retry: false,
  });

  const manuscriptId =
    manuscript.data?.manuscript.id ?? "";

  const versions = useQuery({
    queryKey: [
      "manuscript-versions",
      reportId,
      manuscriptId,
    ],
    queryFn: () =>
      api.manuscriptVersions(
        reportId,
        manuscriptId,
      ),
    enabled:
      !!reportId &&
      !!manuscriptId,
    retry: false,
  });

  const validation = useQuery({
    queryKey: [
      "manuscript-validation",
      reportId,
    ],
    queryFn: () =>
      api.validateManuscript(
        reportId,
      ),
    enabled:
      !!reportId &&
      !!manuscript.data,
    retry: false,
  });

  const section = useQuery({
    queryKey: [
      "manuscript-section",
      reportId,
      selectedSectionKey,
    ],
    queryFn: () =>
      api.manuscriptSection(
        reportId,
        selectedSectionKey,
      ),
    enabled:
      !!reportId &&
      !!selectedSectionKey,
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () =>
      api.generateManuscript(
        reportId,
        false,
        true,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript",
          reportId,
        ],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-versions",
          reportId,
          manuscriptId,
        ],
      });

      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-validation",
          reportId,
        ],
      });
    },
  });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  const current = manuscript.data;
  const sections =
    current?.sections ?? [];
  const dependencies =
    current?.dependencies ?? [];
  const researchOrder =
    current?.research_order ?? [];
  const retrievalIntents =
    section.data?.research_contract
      .retrieval_intents ?? [];
  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Manuscript architecture
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Manuscript
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Manuscript generation, immutable versions,
          section architecture, research ordering, and
          persisted validation are connected directly to
          the M27 backend.
        </p>
      </header>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <div className="muted text-sm">
              Report
            </div>

            <select
              className="input mt-2 min-w-80"
              value={reportId}
              onChange={(event) => {
                setReportId(
                  event.target.value,
                );
                setSelectedSectionKey("");
              }}
            >
              {(
                reports.data ?? []
              ).map((report) => (
                <option
                  key={report.id}
                  value={report.id}
                >
                  {report.topic}
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn btn-primary self-end"
            disabled={
              !reportId ||
              generate.isPending
            }
            onClick={() =>
              generate.mutate()
            }
          >
            {generate.isPending
              ? "Generating…"
              : "Generate manuscript"}
          </button>
        </div>

        {generate.data && (
          <div className="muted text-sm mt-4">
            Generation status:{" "}
            {generate.data.status}
            {generate.data.job_id
              ? " · job " +
                generate.data.job_id
              : ""}
            {generate.data.version_id
              ? " · version " +
                generate.data.version_id
              : ""}
          </div>
        )}

        {generate.error && (
          <div
            className="text-sm mt-3"
            style={{
              color: "var(--danger)",
            }}
          >
            {generate.error.message}
          </div>
        )}
      </section>

      {manuscript.isPending && (
        <div className="card p-6 muted">
          Loading manuscript…
        </div>
      )}

      {manuscript.error && (
        <div className="card p-6">
          <div
            style={{
              color: "var(--danger)",
            }}
          >
            Manuscript unavailable:{" "}
            {manuscript.error.message}
          </div>

          <div className="muted text-sm mt-2">
            Generate a manuscript for this report
            when the report is ready.
          </div>
        </div>
      )}

      {current && (
        <>
          <div className="grid md:grid-cols-4 gap-4">
            <Metric
              label="Status"
              value={
                current.manuscript.status
              }
            />

            <Metric
              label="Current version"
              value={
                `v${current.version.version}`
              }
            />

            <Metric
              label="Sections"
              value={sections.length}
            />

            <Metric
              label="Word target"
              value={
                current.version.word_target
              }
            />
          </div>

          <section className="card p-5">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Current manuscript
                </h2>

                <p className="muted text-sm mt-1">
                  {
                    current.version.title
                  }
                </p>
              </div>

              <div className="muted text-xs break-all">
                Context hash:{" "}
                {current.version.context_hash}
              </div>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
              <Meta
                label="Architecture"
                value={
                  current.version
                    .architecture_version
                }
              />

              <Meta
                label="Template"
                value={
                  current.version
                    .template_version
                }
              />

              <Meta
                label="Research plan"
                value={
                  `${current.version.research_plan_version}`
                }
              />

              <Meta
                label="Manuscript state"
                value={
                  current.version.status
                }
              />
            </div>

            {current.version.title_rationale && (
              <div className="mt-5">
                <div className="muted text-xs">
                  Title rationale
                </div>

                <p className="text-sm mt-1">
                  {
                    current.version
                      .title_rationale
                  }
                </p>
              </div>
            )}
          </section>

          <div className="grid lg:grid-cols-2 gap-5">
            <section className="card p-5">
              <h2 className="font-semibold">
                Section architecture
              </h2>

              <div className="mt-4 space-y-3">
                {sections.map(
                  (item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="w-full text-left rounded-xl border p-4"
                      style={{
                        borderColor:
                          selectedSectionKey ===
                          item.section_key
                            ? "var(--foreground)"
                            : "var(--line)",
                      }}
                      onClick={() =>
                        setSelectedSectionKey(
                          item.section_key,
                        )
                      }
                    >
                      <div className="flex justify-between gap-4">
                        <div>
                          <div className="font-medium">
                            {item.display_order}.{" "}
                            {item.title}
                          </div>

                          <div className="muted text-xs mt-1">
                            {item.section_key} ·{" "}
                            {item.section_type}
                          </div>
                        </div>

                        <div className="muted text-xs text-right">
                          {item.word_budget} words
                          <br />
                          target{" "}
                          {(
                            item.evidence_coverage_target *
                            100
                          ).toFixed(0)}
                          %
                        </div>
                      </div>

                      <div className="muted text-xs mt-3">
                        {item.required
                          ? "Required"
                          : "Optional"}{" "}
                        ·{" "}
                        {item.citation_required
                          ? "Citation required"
                          : "Citation optional"}{" "}
                        · {item.status}
                      </div>
                    </button>
                  ),
                )}

                {!sections.length && (
                  <div className="muted text-sm">
                    No manuscript sections
                    returned.
                  </div>
                )}
              </div>
            </section>

            <section className="card p-5">
              <h2 className="font-semibold">
                Research order
              </h2>

              <p className="muted text-sm mt-1">
                Backend-derived section ordering
                based on persisted dependencies.
              </p>

              <div className="mt-4 space-y-2">
                {researchOrder.map(
                  (key, index) => (
                    <div
                      key={key + index}
                      className="rounded-xl border p-3"
                      style={{
                        borderColor:
                          "var(--line)",
                      }}
                    >
                      <span className="muted text-xs">
                        {index + 1}
                      </span>{" "}
                      <span className="font-medium">
                        {key}
                      </span>
                    </div>
                  ),
                )}

                {!researchOrder.length && (
                  <div className="muted text-sm">
                    No research order returned.
                  </div>
                )}
              </div>

              <h3 className="font-medium mt-6">
                Dependencies
              </h3>

              <div className="mt-3 space-y-2">
                {dependencies.map(
                  (dependency) => (
                    <div
                      key={dependency.id}
                      className="rounded-xl border p-3 text-sm"
                      style={{
                        borderColor:
                          "var(--line)",
                      }}
                    >
                      <div className="break-all">
                        {dependency.upstream_section_id}
                      </div>

                      <div className="muted text-xs mt-1">
                        ↓{" "}
                        {
                          dependency.dependency_type
                        }
                      </div>

                      <div className="break-all mt-1">
                        {
                          dependency.downstream_section_id
                        }
                      </div>
                    </div>
                  ),
                )}

                {!dependencies.length && (
                  <div className="muted text-sm">
                    No persisted dependencies.
                  </div>
                )}
              </div>
            </section>
          </div>

          {selectedSectionKey && (
            <section className="card p-5">
              <h2 className="font-semibold">
                Section detail
              </h2>

              {section.isPending && (
                <div className="muted text-sm mt-4">
                  Loading section…
                </div>
              )}

              {section.error && (
                <div
                  className="text-sm mt-4"
                  style={{
                    color:
                      "var(--danger)",
                  }}
                >
                  {section.error.message}
                </div>
              )}

              {section.data && (
                <div className="mt-4">
                  <div className="grid md:grid-cols-3 gap-4">
                    <Meta
                      label="Section"
                      value={
                        section.data
                          .section_key
                      }
                    />

                    <Meta
                      label="Type"
                      value={
                        section.data
                          .section_type
                      }
                    />

                    <Meta
                      label="Status"
                      value={
                        section.data.status
                      }
                    />
                  </div>

                  {section.data.purpose && (
                    <TextBlock
                      label="Purpose"
                      value={
                        section.data
                          .purpose
                      }
                    />
                  )}

                  {section.data.research_objective && (
                    <TextBlock
                      label="Research objective"
                      value={
                        section.data
                          .research_objective
                      }
                    />
                  )}

                  {section.data.writing_objective && (
                    <TextBlock
                      label="Writing objective"
                      value={
                        section.data
                          .writing_objective
                      }
                    />
                  )}

                  <div className="grid md:grid-cols-3 gap-4 mt-5">
                    <Metric
                      label="Word budget"
                      value={
                        section.data
                          .word_budget
                      }
                    />

                    <Metric
                      label="Budget weight"
                      value={
                        section.data
                          .budget_weight
                          .toFixed(2)
                      }
                    />

                    <Metric
                      label="Coverage target"
                      value={
                        (
                          section.data
                            .evidence_coverage_target *
                          100
                        ).toFixed(1) +
                        "%"
                      }
                    />
                  </div>

                  <div className="mt-6">
                    <h3 className="font-medium">
                      Retrieval intents
                    </h3>

                    <div className="flex flex-wrap gap-2 mt-3">
                      {retrievalIntents.map((intent) => (
                        <span
                          key={intent}
                          className="rounded-full border px-3 py-1 text-xs"
                        >
                          {intent}
                        </span>
                      ))}

                      {!retrievalIntents.length && (
                        <span className="muted text-sm">
                          No retrieval intents.
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

          <section className="card p-5">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Version history
                </h2>

                <p className="muted text-sm mt-1">
                  Immutable manuscript versions
                  returned by the collaboration/version
                  service.
                </p>
              </div>

              <Metric
                label="Total versions"
                value={
                  versions.data?.total ??
                  "—"
                }
              />
            </div>

            <div className="mt-5 space-y-3">
              {versions.isPending && (
                <div className="muted text-sm">
                  Loading versions…
                </div>
              )}

              {(
                versions.data?.items ??
                []
              ).map((version) => (
                <div
                  key={version.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="flex flex-wrap justify-between gap-3">
                    <div>
                      <div className="font-medium">
                        v{version.version} ·{" "}
                        {version.title}
                      </div>

                      <div className="muted text-xs mt-1">
                        {version.status} ·{" "}
                        {
                          version.architecture_version
                        }{" "}
                        ·{" "}
                        {
                          version.template_version
                        }
                      </div>
                    </div>

                    <div className="muted text-xs">
                      {
                        version.word_target
                      }{" "}
                      words
                    </div>
                  </div>

                  <div className="muted text-xs mt-2 break-all">
                    {version.id}
                  </div>
                </div>
              ))}

              {!versions.isPending &&
                !versions.data?.items
                  .length && (
                  <div className="muted text-sm">
                    No manuscript versions
                    returned.
                  </div>
                )}
            </div>
          </section>

          <section className="card p-5">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Manuscript validation
                </h2>

                <p className="muted text-sm mt-1">
                  Validation executes against the
                  persisted current manuscript.
                </p>
              </div>

              {validation.data && (
                <span className="rounded-full border px-3 py-1 text-xs">
                  {
                    validation.data
                      .validation_status
                  }
                </span>
              )}
            </div>

            {validation.isPending && (
              <div className="muted text-sm mt-4">
                Validating manuscript…
              </div>
            )}

            {validation.error && (
              <div
                className="text-sm mt-4"
                style={{
                  color:
                    "var(--danger)",
                }}
              >
                {validation.error.message}
              </div>
            )}

            {validation.data && (
              <div className="mt-5">
                {validation.data
                  .validation_errors
                  ?.length ? (
                  <div>
                    <h3 className="font-medium">
                      Validation errors
                    </h3>

                    <div className="mt-3 space-y-2">
                      {validation.data.validation_errors.map(
                        (error, index) => (
                          <div
                            key={index}
                            className="rounded-xl border p-3 text-sm"
                            style={{
                              borderColor:
                                "var(--danger)",
                            }}
                          >
                            {error}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-sm">
                    No validation errors.
                  </div>
                )}

                {!!validation.data
                  .warnings?.length && (
                  <div className="mt-5">
                    <h3 className="font-medium">
                      Warnings
                    </h3>

                    <div className="mt-3 space-y-2">
                      {validation.data.warnings.map(
                        (warning, index) => (
                          <div
                            key={index}
                            className="rounded-xl border p-3 text-sm"
                            style={{
                              borderColor:
                                "var(--line)",
                            }}
                          >
                            {warning}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="card p-4">
      <div className="muted text-sm">
        {label}
      </div>

      <div className="text-xl font-semibold mt-2">
        {value}
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="muted text-xs">
        {label}
      </div>

      <div className="mt-1 break-all">
        {value}
      </div>
    </div>
  );
}

function TextBlock({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="mt-5">
      <div className="muted text-xs">
        {label}
      </div>

      <p className="text-sm mt-1 whitespace-pre-wrap">
        {value}
      </p>
    </div>
  );
}