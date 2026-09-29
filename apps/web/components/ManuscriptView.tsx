"use client";

import Link from "next/link";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import {
  commitManuscriptDraft,
  discardManuscriptDraft,
  getCurrentManuscript,
  getManuscriptDraft,
  getCurrentManuscriptProse,
  listManuscriptVersions,
  generateManuscript,
  saveManuscriptDraft,
  validateManuscript,
  ManuscriptDraftConflictError,
  type ManuscriptCurrent,
  type ManuscriptDraft,
} from "@/lib/api/manuscript";

type DraftSection = {
  section_key: string;
  title: string;
  purpose: string | null;
  display_order: number;
  word_budget: number;
};

type DraftContent = {
  title: string;
  word_target: number;
  abstract_direction: Record<string, unknown> | null;
  sections: DraftSection[];
};

function buildBaseDraft(current: ManuscriptCurrent): DraftContent {
  return {
    title: current.version.title,
    word_target: current.version.word_target,
    abstract_direction: current.version.abstract_direction,
    sections: current.sections.map((section) => ({
      section_key: section.section_key,
      title: section.title,
      purpose: section.purpose,
      display_order: section.display_order,
      word_budget: section.word_budget,
    })),
  };
}

function mergeDraft(
  current: ManuscriptCurrent,
  draft: ManuscriptDraft,
): DraftContent {
  const base = buildBaseDraft(current);
  const rawSections = Array.isArray(draft.content.sections)
    ? draft.content.sections
    : [];
  const overrides = new Map<string, Record<string, unknown>>();

  for (const item of rawSections) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const key =
      typeof record.section_key === "string"
        ? record.section_key.trim()
        : "";
    if (key) overrides.set(key, record);
  }

  return {
    title:
      typeof draft.content.title === "string"
        ? draft.content.title
        : base.title,
    word_target:
      typeof draft.content.word_target === "number"
        ? Math.max(0, draft.content.word_target)
        : base.word_target,
    abstract_direction:
      draft.content.abstract_direction &&
      typeof draft.content.abstract_direction === "object"
        ? (draft.content.abstract_direction as Record<string, unknown>)
        : base.abstract_direction,
    sections: base.sections.map((section) => {
      const override = overrides.get(section.section_key);
      return {
        ...section,
        title:
          typeof override?.title === "string"
            ? override.title
            : section.title,
        purpose:
          override && Object.prototype.hasOwnProperty.call(override, "purpose")
            ? typeof override.purpose === "string"
              ? override.purpose
              : null
            : section.purpose,
        word_budget:
          typeof override?.word_budget === "number"
            ? Math.max(0, override.word_budget)
            : section.word_budget,
      };
    }),
  };
}

function fingerprint(content: DraftContent): string {
  return JSON.stringify(content);
}

export default function ManuscriptView() {
  const queryClient = useQueryClient();
  const {
    reportId: activeReportId,
    workspacesQuery: workspaces,
    projectsQuery: projects,
    reportsQuery: reports,
    contextHref,
  } = useResearchContext();

  const [draftContent, setDraftContent] = useState<DraftContent | null>(null);
  const [baseVersionId, setBaseVersionId] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const draftContentRef = useRef<DraftContent | null>(null);
  const lastSentFingerprintRef = useRef<string | null>(null);

  const manuscript = useQuery({
    queryKey: ["manuscript-current", activeReportId],
    queryFn: () => getCurrentManuscript(activeReportId!),
    enabled: Boolean(activeReportId),
    staleTime: 10_000,
  });

  const draft = useQuery({
    queryKey: ["manuscript-draft", activeReportId],
    queryFn: () => getManuscriptDraft(activeReportId!),
    enabled: Boolean(activeReportId && manuscript.data),
    staleTime: 2_000,
  });

  const prose = useQuery({
    queryKey: ["manuscript-prose-current", activeReportId],
    queryFn: () => getCurrentManuscriptProse(activeReportId!),
    enabled: Boolean(activeReportId && manuscript.data),
    staleTime: 10_000,
  });

  const versions = useQuery({
    queryKey: ["manuscript-versions", activeReportId],
    queryFn: () => listManuscriptVersions(activeReportId!),
    enabled: Boolean(activeReportId && manuscript.data),
    staleTime: 10_000,
  });

  const generate = useMutation({
    mutationFn: () => generateManuscript(activeReportId!, false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-draft", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-prose-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-versions", activeReportId],
      });
    },
  });

  const validate = useMutation({
    mutationFn: () => validateManuscript(activeReportId!),
  });

  const autosave = useMutation({
    mutationFn: (input: {
      baseVersionId: string;
      revision: number;
      content: DraftContent;
    }) =>
      saveManuscriptDraft(activeReportId!, {
        baseVersionId: input.baseVersionId,
        revision: input.revision,
        content: input.content as unknown as Record<string, unknown>,
      }),
    onMutate: (variables) => {
      lastSentFingerprintRef.current = fingerprint(variables.content);
      setNotice(null);
    },
    onSuccess: (data, variables) => {
      setRevision(data.revision);
      queryClient.setQueryData(
        ["manuscript-draft", activeReportId],
        data,
      );
      const latest = draftContentRef.current;
      if (latest && fingerprint(latest) === lastSentFingerprintRef.current) {
        setDirty(false);
      } else {
        setDirty(true);
      }
      setConflict(false);
      setNotice(
        data.revision === 0
          ? "Draft autosaved."
          : `Draft autosaved · revision ${data.revision}`,
      );
    },
    onError: (error) => {
      if (error instanceof ManuscriptDraftConflictError) {
        setConflict(true);
        setNotice("Draft conflict detected. Reload the latest manuscript before saving again.");
        return;
      }
      setNotice(
        error instanceof Error
          ? `Autosave failed: ${error.message}`
          : "Autosave failed.",
      );
    },
  });

  const commit = useMutation({
    mutationFn: () =>
      commitManuscriptDraft(
        activeReportId!,
        baseVersionId!,
        revision,
      ),
    onSuccess: async (version) => {
      setNotice(`Draft committed as manuscript version ${version.version}.`);
      setDirty(false);
      setConflict(false);
      setRevision(0);
      setBaseVersionId(null);
      setDraftContent(null);
      queryClient.setQueryData(
        ["manuscript-draft", activeReportId],
        null,
      );
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-versions", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-prose-current", activeReportId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-draft", activeReportId],
      });
    },
    onError: (error) => {
      if (error instanceof ManuscriptDraftConflictError) {
        setConflict(true);
        setNotice("The draft became stale while committing. Reload the latest manuscript.");
        return;
      }
      setNotice(
        error instanceof Error
          ? `Commit failed: ${error.message}`
          : "Commit failed.",
      );
    },
  });

  const autosavePending = autosave.isPending;
  const autosaveMutate = autosave.mutate;

  const discard = useMutation({
    mutationFn: () => discardManuscriptDraft(activeReportId!),
    onSuccess: async () => {
      setDraftContent(manuscript.data ? buildBaseDraft(manuscript.data) : null);
      setBaseVersionId(manuscript.data?.version.id ?? null);
      setRevision(0);
      setDirty(false);
      setConflict(false);
      setNotice("Autosaved draft discarded.");
      await queryClient.invalidateQueries({
        queryKey: ["manuscript-draft", activeReportId],
      });
    },
  });

  useEffect(() => {
    draftContentRef.current = draftContent;
  }, [draftContent]);

  useEffect(() => {
    const current = manuscript.data;
    if (!current || draft.isPending) return;
    if (baseVersionId === current.version.id) return;

    const recovered =
      draft.data && draft.data.base_version_id === current.version.id
        ? draft.data
        : null;
    const nextContent = recovered
      ? mergeDraft(current, recovered)
      : buildBaseDraft(current);

    setDraftContent(nextContent);
    setBaseVersionId(current.version.id);
    setRevision(recovered?.revision ?? 0);
    setDirty(Boolean(recovered));
    setConflict(false);
    setNotice(
      recovered
        ? `Recovered autosaved draft · revision ${recovered.revision}`
        : null,
    );
    lastSentFingerprintRef.current = recovered
      ? fingerprint(nextContent)
      : null;
  }, [
    baseVersionId,
    draft.data,
    draft.isPending,
    manuscript.data,
  ]);

  useEffect(() => {
    if (
      !activeReportId ||
      !baseVersionId ||
      !draftContent ||
      !dirty ||
      conflict ||
      autosavePending
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      autosaveMutate({
        baseVersionId,
        revision,
        content: draftContent,
      });
    }, 900);

    return () => window.clearTimeout(timer);
  }, [
    activeReportId,
    autosaveMutate,
    autosavePending,
    baseVersionId,
    conflict,
    dirty,
    draftContent,
    revision,
  ]);

  const errors = [
    workspaces.error,
    projects.error,
    reports.error,
    manuscript.error,
    draft.error,
    prose.error,
    versions.error,
    generate.error,
    validate.error,
    commit.error,
    discard.error,
  ].filter(Boolean);

  const firstError = errors.find(
    (error): error is Error => error instanceof Error,
  );
  if (firstError) {
    return (
      <section className="card pad" role="alert">
        <h2>Manuscript unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {firstError.message}
        </p>
      </section>
    );
  }

  const current = manuscript.data;
  const canCommit =
    Boolean(activeReportId && draft.data && baseVersionId && !conflict) &&
    !autosave.isPending &&
    !commit.isPending &&
    revision >= 0;
  const canManualSave =
    Boolean(activeReportId && draftContent && baseVersionId && !conflict) &&
    !autosave.isPending &&
    !commit.isPending &&
    dirty;

  const statusText = conflict
    ? "Conflict"
    : autosave.isPending
      ? "Saving…"
      : dirty
        ? "Unsaved changes"
        : draft.data
          ? `Saved revision ${draft.data.revision}`
          : "No draft";

  async function reloadLatest() {
    setBaseVersionId(null);
    setDraftContent(null);
    setRevision(0);
    setDirty(false);
    setConflict(false);
    setNotice(null);
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["manuscript-current", activeReportId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["manuscript-draft", activeReportId],
      }),
    ]);
  }

  function updateDraft(
    updater: (previous: DraftContent) => DraftContent,
  ) {
    setDraftContent((previous) => {
      if (!previous) return previous;
      return updater(previous);
    });
    setDirty(true);
    setNotice(null);
  }

  const sections = current?.sections ?? [];
  const draftSections = draftContent?.sections ?? [];

  const draftByKey = useMemo(
    () => new Map(draftSections.map((section) => [section.section_key, section])),
    [draftSections],
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Manuscript architect · M27/F08</div>
            <h2 style={{ marginTop: 4 }}>
              {current?.version.title ?? "Manuscript"}
            </h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Edit the manuscript architecture in a persisted autosave draft.
              Immutable manuscript versions are created only when the draft is
              explicitly committed.
            </p>
          </div>
          <div className="actions">
            <span className={`tag ${conflict ? "" : dirty ? "" : "success"}`}>
              {statusText}
            </span>
            <button
              className="btn"
              type="button"
              disabled={!activeReportId || validate.isPending}
              onClick={() => validate.mutate()}
            >
              {validate.isPending ? "Validating…" : "Validate"}
            </button>
            <Link className="btn primary" href={contextHref("/generate")}>
              AI Studio
            </Link>
          </div>
        </div>
      </section>

      {!activeReportId && !reports.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No research report exists in this project yet.</div>
          <Link
            className="btn"
            href={contextHref("/research")}
            style={{ marginTop: 12 }}
          >
            Open Research
          </Link>
        </section>
      )}

      {activeReportId && !current && !manuscript.isPending && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>No manuscript has been generated for this report yet.</div>
          <button
            className="btn primary"
            style={{ marginTop: 12 }}
            disabled={generate.isPending}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? "Generating…" : "Generate manuscript"}
          </button>
          {generate.data && (
            <div className="muted small" style={{ marginTop: 10 }}>
              {generate.data.status}
              {generate.data.section_count != null
                ? " · " + generate.data.section_count + " sections"
                : ""}
            </div>
          )}
        </section>
      )}

      {current && draftContent && (
        <>
          {notice && (
            <section
              className="card pad"
              role={conflict ? "alert" : "status"}
            >
              <div className="row">
                <div>
                  <div className="strong">{conflict ? "Draft conflict" : "Draft status"}</div>
                  <div className="muted small" style={{ marginTop: 4 }}>
                    {notice}
                  </div>
                </div>
                {conflict && (
                  <button
                    className="btn primary"
                    type="button"
                    onClick={() => void reloadLatest()}
                  >
                    Reload latest
                  </button>
                )}
              </div>
            </section>
          )}

          <section className="card pad">
            <div className="row">
              <div>
                <h3>Autosave draft</h3>
                <div className="muted small">
                  Base version v{current.version.version} · draft revision {revision}
                </div>
              </div>
              <div className="actions">
                <button
                  className="btn"
                  type="button"
                  disabled={!canManualSave}
                  onClick={() =>
                    autosave.mutate({
                      baseVersionId: baseVersionId!,
                      revision,
                      content: draftContent,
                    })
                  }
                >
                  {autosave.isPending ? "Saving…" : "Save now"}
                </button>
                <button
                  className="btn"
                  type="button"
                  disabled={
                    !activeReportId ||
                    discard.isPending ||
                    (!draft.data && !dirty)
                  }
                  onClick={() => discard.mutate()}
                >
                  {discard.isPending ? "Discarding…" : "Discard draft"}
                </button>
                <button
                  className="btn primary"
                  type="button"
                  disabled={!canCommit || (!draft.data && !dirty)}
                  onClick={() => commit.mutate()}
                >
                  {commit.isPending ? "Committing…" : "Commit as version"}
                </button>
              </div>
            </div>

            <div className="grid grid-2" style={{ marginTop: 14 }}>
              <div className="field">
                <label htmlFor="manuscript-draft-title">Draft title</label>
                <input
                  id="manuscript-draft-title"
                  className="input"
                  value={draftContent.title}
                  disabled={conflict || autosave.isPending}
                  onChange={(event) =>
                    updateDraft((previous) => ({
                      ...previous,
                      title: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="manuscript-draft-word-target">Word target</label>
                <input
                  id="manuscript-draft-word-target"
                  className="input"
                  type="number"
                  min={0}
                  value={draftContent.word_target}
                  disabled={conflict || autosave.isPending}
                  onChange={(event) =>
                    updateDraft((previous) => ({
                      ...previous,
                      word_target: Math.max(
                        0,
                        Number.parseInt(event.target.value || "0", 10) || 0,
                      ),
                    }))
                  }
                />
              </div>
            </div>
          </section>

          <section className="card pad">
            <div className="row">
              <div>
                <h3>Editable section architecture</h3>
                <div className="muted small">
                  Draft edits preserve the backend research contract from the base
                  immutable version.
                </div>
              </div>
              <span className="tag">{draftSections.length} sections</span>
            </div>

            <div className="stack" style={{ marginTop: 12 }}>
              {sections.map((section) => {
                const editable = draftByKey.get(section.section_key);
                if (!editable) return null;
                return (
                  <article className="list-item" key={section.section_key}>
                    <div className="row">
                      <div>
                        <div className="title">
                          {section.display_order}. {section.title}
                        </div>
                        <div className="meta">{section.section_key}</div>
                      </div>
                      <span className="tag">
                        {editable.word_budget} words
                      </span>
                    </div>

                    <div className="grid grid-2" style={{ marginTop: 12 }}>
                      <div className="field">
                        <label
                          htmlFor={`manuscript-draft-section-title-${section.section_key}`}
                        >
                          Section title
                        </label>
                        <input
                          id={`manuscript-draft-section-title-${section.section_key}`}
                          className="input"
                          value={editable.title}
                          disabled={conflict || autosave.isPending}
                          onChange={(event) =>
                            updateDraft((previous) => ({
                              ...previous,
                              sections: previous.sections.map((item) =>
                                item.section_key === section.section_key
                                  ? { ...item, title: event.target.value }
                                  : item,
                              ),
                            }))
                          }
                        />
                      </div>
                      <div className="field">
                        <label
                          htmlFor={`manuscript-draft-section-budget-${section.section_key}`}
                        >
                          Section word budget
                        </label>
                        <input
                          id={`manuscript-draft-section-budget-${section.section_key}`}
                          className="input"
                          type="number"
                          min={0}
                          value={editable.word_budget}
                          disabled={conflict || autosave.isPending}
                          onChange={(event) =>
                            updateDraft((previous) => ({
                              ...previous,
                              sections: previous.sections.map((item) =>
                                item.section_key === section.section_key
                                  ? {
                                      ...item,
                                      word_budget: Math.max(
                                        0,
                                        Number.parseInt(
                                          event.target.value || "0",
                                          10,
                                        ) || 0,
                                      ),
                                    }
                                  : item,
                              ),
                            }))
                          }
                        />
                      </div>
                    </div>

                    <div className="field" style={{ marginTop: 10 }}>
                      <label
                        htmlFor={`manuscript-draft-section-purpose-${section.section_key}`}
                      >
                        Section purpose
                      </label>
                      <textarea
                        id={`manuscript-draft-section-purpose-${section.section_key}`}
                        className="input textarea"
                        value={editable.purpose ?? ""}
                        disabled={conflict || autosave.isPending}
                        onChange={(event) =>
                          updateDraft((previous) => ({
                            ...previous,
                            sections: previous.sections.map((item) =>
                              item.section_key === section.section_key
                                ? {
                                    ...item,
                                    purpose:
                                      event.target.value || null,
                                  }
                                : item,
                            ),
                          }))
                        }
                      />
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="grid grid-3">
            <div className="card metric">
              <div className="label">Immutable version</div>
              <div className="value">v{current.version.version}</div>
              <div className="delta">{current.version.status}</div>
            </div>
            <div className="card metric">
              <div className="label">Draft revision</div>
              <div className="value">{revision}</div>
              <div className="delta">Optimistic concurrency token</div>
            </div>
            <div className="card metric">
              <div className="label">Sections</div>
              <div className="value">{sections.length}</div>
              <div className="delta">{current.research_order.length} in research order</div>
            </div>
          </section>

          <section className="card pad">
            <div className="row">
              <h3>Current prose</h3>
              <span className="tag">{prose.data?.run.word_count ?? 0} words</span>
            </div>
            {!prose.data && !prose.isPending && (
              <div className="empty" style={{ marginTop: 12 }}>
                <div className="big">∅</div>
                <div>No completed prose run exists for this manuscript yet.</div>
              </div>
            )}
            {(prose.data?.sections ?? []).map((section) => (
              <article
                className="list-item"
                key={section.id}
                style={{ marginTop: 10 }}
              >
                <div className="row">
                  <div className="title">
                    {section.display_order}. {section.title}
                  </div>
                  <span className="tag">{section.status}</span>
                </div>
                <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, marginTop: 8 }}>
                  {section.text}
                </p>
                <div className="meta">
                  {section.word_count} words · {section.paragraph_count} paragraphs
                </div>
              </article>
            ))}
          </section>

          <section className="card pad">
            <div className="row">
              <h3>Immutable versions</h3>
              <span className="tag">{versions.data?.length ?? 0}</span>
            </div>
            <div className="list" style={{ marginTop: 12 }}>
              {(versions.data ?? []).map((version) => (
                <div className="list-item" key={version.id}>
                  <div className="row">
                    <span className="title">
                      v{version.version} · {version.title}
                    </span>
                    <span className="tag">{version.status}</span>
                  </div>
                  <div className="meta">
                    {version.word_target} word target · {version.created_at}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {validate.data && (
        <section className="card pad" role="status">
          Validation: <b>{validate.data.validation_status}</b>
          {(validate.data.warnings?.length ?? 0) > 0 && (
            <span className="muted"> · {validate.data.warnings?.join(" · ")}</span>
          )}
        </section>
      )}
    </div>
  );
}
