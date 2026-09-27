"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

const languageOptions = [
  { code: "en", label: "English" },
  { code: "fa", label: "Persian" },
  { code: "de", label: "German" },
  { code: "fr", label: "French" },
  { code: "es", label: "Spanish" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "tr", label: "Turkish" },
  { code: "ar", label: "Arabic" },
];

export default function TranslationPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [reportId, setReportId] =
    useState("");

  const [targetLanguage, setTargetLanguage] =
    useState("fa");

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
    queryKey: [
      "manuscript",
      reportId,
    ],
    queryFn: () =>
      api.manuscript(reportId),
    enabled: !!reportId,
    retry: false,
  });

  const jobs = useQuery({
    queryKey: ["jobs", workspaceId],
    queryFn: api.jobs,
    enabled: !!workspaceId,
  });

  const enqueue = useMutation({
    mutationFn: () => {
      const sourceVersionId =
        manuscript.data?.version.id;

      if (!sourceVersionId) {
        throw new Error(
          "No current manuscript version is available.",
        );
      }

      return api.enqueueTranslation(
        reportId,
        {
          source_version_id:
            sourceVersionId,
          target_language:
            targetLanguage,
        },
      );
    },

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "jobs",
          workspaceId,
        ],
      });
    },
  });

  const translationJobs =
    useMemo(
      () =>
        (jobs.data ?? []).filter(
          (job) =>
            job.job_type
              .toLowerCase()
              .includes("translation"),
        ),
      [jobs.data],
    );

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  const currentVersion =
    manuscript.data?.version;

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Translation workflow
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Translation
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Translation requests use the current
          manuscript version and are submitted as durable
          backend jobs. Provider routing remains
          server-side.
        </p>
      </header>

      <section className="card p-5">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <div className="muted text-sm">
              Report
            </div>

            <select
              className="input mt-2"
              value={reportId}
              onChange={(event) =>
                setReportId(
                  event.target.value,
                )
              }
            >
              {(reports.data ?? []).map(
                (report) => (
                  <option
                    key={report.id}
                    value={report.id}
                  >
                    {report.topic}
                  </option>
                ),
              )}
            </select>
          </div>

          <div>
            <div className="muted text-sm">
              Target language
            </div>

            <select
              className="input mt-2"
              value={targetLanguage}
              onChange={(event) =>
                setTargetLanguage(
                  event.target.value,
                )
              }
            >
              {languageOptions.map(
                (language) => (
                  <option
                    key={language.code}
                    value={language.code}
                  >
                    {language.label}
                  </option>
                ),
              )}
            </select>
          </div>
        </div>
      </section>

      {manuscript.isPending && (
        <div className="card p-6 muted">
          Loading current manuscript…
        </div>
      )}

      {manuscript.error && (
        <section className="card p-6">
          <div
            style={{
              color: "var(--danger)",
            }}
          >
            Manuscript unavailable:{" "}
            {manuscript.error.message}
          </div>
        </section>
      )}

      {currentVersion && (
        <>
          <div className="grid md:grid-cols-4 gap-4">
            <Metric
              label="Version"
              value={`v${currentVersion.version}`}
            />

            <Metric
              label="Status"
              value={currentVersion.status}
            />

            <Metric
              label="Language"
              value={
                manuscript.data?.manuscript
                  .report_id
                  ? (
                      reports.data?.find(
                        (report) =>
                          report.id ===
                          reportId,
                      )?.output_language ??
                      "—"
                    )
                  : "—"
              }
            />

            <Metric
              label="Word target"
              value={
                currentVersion.word_target
              }
            />
          </div>

          <section className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Translation request
                </h2>

                <p className="muted text-sm mt-1">
                  Source version{" "}
                  {currentVersion.id}
                </p>
              </div>

              <button
                className="btn btn-primary"
                disabled={
                  !reportId ||
                  !currentVersion.id ||
                  enqueue.isPending
                }
                onClick={() =>
                  enqueue.mutate()
                }
              >
                {enqueue.isPending
                  ? "Queueing…"
                  : `Translate to ${
                      languageOptions.find(
                        (language) =>
                          language.code ===
                          targetLanguage,
                      )?.label ??
                      targetLanguage
                    }`}
              </button>
            </div>

            <div className="grid md:grid-cols-3 gap-4 mt-5">
              <Meta
                label="Source title"
                value={
                  currentVersion.title
                }
              />

              <Meta
                label="Architecture"
                value={
                  currentVersion
                    .architecture_version
                }
              />

              <Meta
                label="Template"
                value={
                  currentVersion
                    .template_version
                }
              />
            </div>

            {enqueue.data && (
              <div className="rounded-xl border p-4 mt-5">
                <div className="font-medium">
                  Translation queued
                </div>

                <div className="muted text-sm mt-1">
                  Status:{" "}
                  {enqueue.data.status}
                </div>

                <div className="muted text-xs mt-1 break-all">
                  Job:{" "}
                  {enqueue.data.job_id}
                </div>
              </div>
            )}

            {enqueue.error && (
              <div
                className="text-sm mt-4"
                style={{
                  color:
                    "var(--danger)",
                }}
              >
                {enqueue.error.message}
              </div>
            )}
          </section>

          <section className="card p-5">
            <h2 className="font-semibold">
              Current manuscript sections
            </h2>

            <div className="grid md:grid-cols-2 gap-3 mt-4">
              {(
                manuscript.data?.sections ??
                []
              ).map((section) => (
                <div
                  key={section.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="font-medium">
                    {section.title}
                  </div>

                  <div className="muted text-sm mt-1">
                    {section.section_type} ·{" "}
                    {section.word_budget}{" "}
                    words
                  </div>

                  <div className="muted text-xs mt-2">
                    {section.citation_required
                      ? "Citation required"
                      : "Citation optional"}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section className="card overflow-hidden">
        <div
          className="px-5 py-4 border-b"
          style={{
            borderColor:
              "var(--line)",
          }}
        >
          <div className="font-semibold">
            Translation jobs
          </div>

          <div className="muted text-xs mt-1">
            Durable jobs returned by the backend.
          </div>
        </div>

        <div className="divide-y">
          {jobs.isPending && (
            <div className="p-6 muted">
              Loading jobs…
            </div>
          )}

          {!jobs.isPending &&
            !translationJobs.length && (
              <div className="p-8 muted text-sm">
                No translation jobs are currently
                visible.
              </div>
            )}

          {translationJobs.map((job) => (
            <div
              key={job.id}
              className="p-5"
            >
              <div className="flex flex-wrap justify-between gap-4">
                <div>
                  <div className="font-medium">
                    {job.job_type}
                  </div>

                  <div className="muted text-xs mt-1 break-all">
                    {job.id}
                  </div>
                </div>

                <div className="text-right">
                  <div>
                    {job.status}
                  </div>

                  <div className="muted text-xs mt-1">
                    Attempt{" "}
                    {job.attempt_count}/
                    {job.max_attempts}
                  </div>
                </div>
              </div>

              {job.last_error_message && (
                <div
                  className="text-sm mt-3"
                  style={{
                    color:
                      "var(--danger)",
                  }}
                >
                  {
                    job.last_error_message
                  }
                </div>
              )}
            </div>
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
  value: number | string;
}) {
  return (
    <div className="card p-5">
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