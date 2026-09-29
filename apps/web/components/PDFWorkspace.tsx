"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import { projectFileContentUrl } from "@/lib/api/files";
import {
  createPdfAnnotation,
  deletePdfAnnotation,
  getPdfWorkspace,
  savePdfWorkspace,
} from "@/lib/api/pdf-workspace";

export default function PDFWorkspace() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [noteType, setNoteType] = useState<"note" | "highlight">("note");
  const [selectedText, setSelectedText] = useState("");
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState("");
  const queryClient = useQueryClient();

  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
    staleTime: 30_000,
  });

  const activeWorkspaceId = workspaceId ?? workspaces.data?.[0]?.id;

  const projects = useQuery({
    queryKey: ["projects", activeWorkspaceId],
    queryFn: () => {
      if (!activeWorkspaceId) throw new Error("No workspace is selected.");
      return listProjects(activeWorkspaceId);
    },
    enabled: Boolean(activeWorkspaceId),
    staleTime: 15_000,
  });

  const activeProjectId = projectId ?? projects.data?.[0]?.id;

  const workspace = useQuery({
    queryKey: ["pdf-workspace", activeProjectId],
    queryFn: () => getPdfWorkspace(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 5_000,
  });

  useEffect(() => {
    if (!workspace.data) return;
    const timer = window.setTimeout(() => {
      setActiveFileId(workspace.data?.active_file_id ?? null);
      setPageNumber(workspace.data?.page_number ?? 1);
      setZoom(workspace.data?.zoom ?? 1);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [workspace.data]);

  const selectedFile = useMemo(
    () =>
      (workspace.data?.documents ?? []).find(
        (file) => file.id === activeFileId,
      ),
    [activeFileId, workspace.data?.documents],
  );

  const save = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return savePdfWorkspace(activeProjectId, {
        active_file_id: activeFileId,
        page_number: pageNumber,
        zoom,
        scroll_x: 0,
        scroll_y: 0,
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["pdf-workspace", activeProjectId],
        data,
      );
      setFeedback("PDF workspace state saved.");
    },
  });

  const addAnnotation = useMutation({
    mutationFn: () => {
      if (!activeProjectId || !activeFileId) {
        throw new Error("Select a PDF before creating an annotation.");
      }
      if (noteType === "highlight" && !selectedText.trim()) {
        throw new Error("A highlight requires selected text.");
      }
      if (!note.trim()) {
        throw new Error("Add a note before saving the annotation.");
      }
      return createPdfAnnotation(activeProjectId, {
        file_id: activeFileId,
        kind: noteType,
        page_number: pageNumber,
        selected_text: selectedText.trim() || undefined,
        note: note.trim(),
      });
    },
    onSuccess: async () => {
      setSelectedText("");
      setNote("");
      setFeedback("Annotation saved.");
      await queryClient.invalidateQueries({
        queryKey: ["pdf-workspace", activeProjectId],
      });
    },
  });

  const removeAnnotation = useMutation({
    mutationFn: (annotationId: string) => {
      if (!activeProjectId) {
        throw new Error("No project is selected.");
      }
      return deletePdfAnnotation(activeProjectId, annotationId);
    },
    onSuccess: async () => {
      setFeedback("Annotation deleted.");
      await queryClient.invalidateQueries({
        queryKey: ["pdf-workspace", activeProjectId],
      });
    },
  });

  const error = [
    workspaces.error,
    projects.error,
    workspace.error,
    save.error,
    addAnnotation.error,
    removeAnnotation.error,
  ].find((value): value is Error => value instanceof Error);

  if (error) {
    return (
      <section className="card pad" role="alert">
        <h2>PDF workspace unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {error.message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 12 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void workspace.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Legacy Phase 12</div>
            <h2 style={{ marginTop: 4 }}>PDF Research Workspace</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Persistent PDF selection, viewer position, highlights and notes.
            </p>
          </div>
          <Link className="btn" href="/files">
            Manage files
          </Link>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="pdf-workspace-workspace">Workspace</label>
            <select
              id="pdf-workspace-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="pdf-workspace-project">Project</label>
            <select
              id="pdf-workspace-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => {
                setProjectId(event.target.value);
                setActiveFileId(null);
                setPageNumber(1);
                setZoom(1);
              }}
              disabled={projects.isPending}
            >
              {(projects.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="pdf-workspace-file">PDF document</label>
            <select
              id="pdf-workspace-file"
              className="input"
              value={activeFileId ?? ""}
              onChange={(event) => {
                setActiveFileId(event.target.value || null);
                setPageNumber(1);
              }}
              disabled={workspace.isPending}
            >
              <option value="">Select a PDF</option>
              {(workspace.data?.documents ?? []).map((file) => (
                <option key={file.id} value={file.id}>
                  {file.original_filename}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {!workspace.isPending &&
        (workspace.data?.documents.length ?? 0) === 0 && (
          <section className="card pad empty">
            <div className="big">∅</div>
            <div>No PDF is stored in this project yet.</div>
            <Link
              className="btn"
              href="/files"
              style={{ marginTop: 12 }}
            >
              Upload a PDF
            </Link>
          </section>
        )}

      {selectedFile && activeProjectId && (
        <>
          <section className="grid grid-2">
            <div className="card pad">
              <div className="row">
                <div>
                  <h3>Document Viewer</h3>
                  <p className="muted small">
                    {selectedFile.original_filename} ·{" "}
                    {selectedFile.extraction_status}
                  </p>
                </div>
                <a
                  className="btn ghost"
                  href={projectFileContentUrl(selectedFile.id)}
                >
                  Open file
                </a>
              </div>

              <div
                style={{
                  marginTop: 12,
                  height: 520,
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <iframe
                  title="PDF document viewer"
                  src={projectFileContentUrl(selectedFile.id)}
                  style={{
                    width: "100%",
                    height: "100%",
                    border: 0,
                  }}
                />
              </div>
            </div>

            <div className="card pad">
              <h3>Persistent view state</h3>
              <p className="muted small" style={{ marginTop: 4 }}>
                Page and zoom are stored server-side and restored after reload.
              </p>

              <div className="grid grid-2" style={{ marginTop: 14 }}>
                <div className="field">
                  <label htmlFor="pdf-page">Page</label>
                  <input
                    id="pdf-page"
                    className="input"
                    type="number"
                    min={1}
                    value={pageNumber}
                    onChange={(event) =>
                      setPageNumber(Math.max(1, Number(event.target.value) || 1))
                    }
                  />
                </div>

                <div className="field">
                  <label htmlFor="pdf-zoom">Zoom</label>
                  <input
                    id="pdf-zoom"
                    className="input"
                    type="number"
                    min={0.25}
                    max={4}
                    step={0.25}
                    value={zoom}
                    onChange={(event) =>
                      setZoom(
                        Math.min(
                          4,
                          Math.max(0.25, Number(event.target.value) || 1),
                        ),
                      )
                    }
                  />
                </div>
              </div>

              <button
                className="btn primary"
                type="button"
                style={{ marginTop: 12 }}
                disabled={save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Saving…" : "Save view state"}
              </button>

              {feedback && (
                <p className="muted small" role="status" style={{ marginTop: 10 }}>
                  {feedback}
                </p>
              )}
            </div>
          </section>

          <section className="card pad">
            <div className="row">
              <div>
                <h3>Highlights & notes</h3>
                <p className="muted small" style={{ marginTop: 4 }}>
                  Annotations are persisted against this PDF and page.
                </p>
              </div>
              <span className="tag">
                {(workspace.data?.annotations ?? []).length} saved
              </span>
            </div>

            <div className="grid grid-3" style={{ marginTop: 14 }}>
              <div className="field">
                <label htmlFor="pdf-annotation-type">Type</label>
                <select
                  id="pdf-annotation-type"
                  className="input"
                  value={noteType}
                  onChange={(event) =>
                    setNoteType(event.target.value as "note" | "highlight")
                  }
                >
                  <option value="note">Note</option>
                  <option value="highlight">Highlight</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="pdf-selected-text">Selected text</label>
                <input
                  id="pdf-selected-text"
                  className="input"
                  value={selectedText}
                  onChange={(event) => setSelectedText(event.target.value)}
                  placeholder="Text from the paper"
                />
              </div>

              <div className="field">
                <label htmlFor="pdf-annotation-note">Note</label>
                <input
                  id="pdf-annotation-note"
                  className="input"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Why this matters"
                />
              </div>
            </div>

            <button
              className="btn"
              type="button"
              style={{ marginTop: 12 }}
              disabled={addAnnotation.isPending}
              onClick={() => addAnnotation.mutate()}
            >
              {addAnnotation.isPending ? "Saving…" : "Save annotation"}
            </button>

            <div className="list" style={{ marginTop: 14 }}>
              {(workspace.data?.annotations ?? []).map((annotation) => (
                <article className="list-item" key={annotation.id}>
                  <div className="row">
                    <div style={{ minWidth: 0 }}>
                      <div className="title">
                        {annotation.kind} · page {annotation.page_number}
                      </div>
                      {annotation.selected_text && (
                        <div className="meta">
                          {annotation.selected_text}
                        </div>
                      )}
                      {annotation.note && (
                        <div style={{ marginTop: 4 }}>{annotation.note}</div>
                      )}
                    </div>
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={removeAnnotation.isPending}
                      onClick={() =>
                        removeAnnotation.mutate(annotation.id)
                      }
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}

              {(workspace.data?.annotations.length ?? 0) === 0 && (
                <div className="empty">
                  <div className="big">∅</div>
                  <div>No annotations saved for this PDF yet.</div>
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
