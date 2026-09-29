"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { listProjects } from "@/lib/api/projects";
import { listWorkspaces } from "@/lib/api/workspaces";
import {
  createProjectFolder,
  deleteProjectFile,
  listProjectFiles,
  listProjectFolders,
  moveProjectFile,
  projectFileContentUrl,
  uploadProjectFile,
} from "@/lib/api/files";
import { getProjectFileEvidence, type ProjectFileEvidence } from "@/lib/api/project-file-evidence";

function evidenceLabel(item: ProjectFileEvidence | undefined): string {
  if (!item) return "Not evaluated";
  if (item.evidence_status === "synced") {
    return "Synced · " + item.chunk_count + " chunks";
  }
  if (item.evidence_status === "awaiting_report") return "Waiting for report";
  if (item.evidence_status === "unavailable") return "Unavailable";
  return "Processing";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

export default function FilesWorkspace() {
  const [workspaceId, setWorkspaceId] = useState<string>();
  const [projectId, setProjectId] = useState<string>();
  const [folderId, setFolderId] = useState<string>();
  const [folderName, setFolderName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
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

  const folders = useQuery({
    queryKey: ["folders", activeProjectId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listProjectFolders(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const evidence = useQuery({
    queryKey: ["project-file-evidence", activeProjectId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return getProjectFileEvidence(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const files = useQuery({
    queryKey: ["files", activeProjectId, folderId],
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listProjectFiles(activeProjectId, folderId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const createFolder = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return createProjectFolder(
        activeProjectId,
        folderName.trim(),
        folderId,
      );
    },
    onSuccess: async () => {
      setFolderName("");
      await queryClient.invalidateQueries({
        queryKey: ["folders", activeProjectId],
      });
    },
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return uploadProjectFile(activeProjectId, file, folderId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["files", activeProjectId],
      });
    },
  });

  const move = useMutation({
    mutationFn: ({
      fileId,
      folderId,
    }: {
      fileId: string;
      folderId?: string;
    }) => moveProjectFile(fileId, folderId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["files", activeProjectId],
      });
    },
  });

  const remove = useMutation({
    mutationFn: (fileId: string) => deleteProjectFile(fileId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["files", activeProjectId],
      });
    },
  });

  const errors = [
    workspaces.error,
    projects.error,
    folders.error,
    evidence.error,
    files.error,
    createFolder.error,
    upload.error,
    move.error,
    remove.error,
  ].filter(Boolean);

  if (errors.length) {
    return (
      <section className="card pad" role="alert">
        <h2>Files unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {(errors[0] as Error).message}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspaces.refetch();
            void projects.refetch();
            void folders.refetch();
            void files.refetch();
            void evidence.refetch();
          }}
        >
          Retry
        </button>
      </section>
    );
  }

  const evidenceByFileId = new Map(
    (evidence.data?.items ?? []).map((item) => [item.file_id, item]),
  );

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Project files</div>
            <h2 style={{ marginTop: 4 }}>Files & intelligence</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Files, folders and processing state returned by the project
              storage API.
            </p>
          </div>
          <span className="tag success">Real data</span>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="files-workspace">Workspace</label>
            <select
              id="files-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspaceId(event.target.value);
                setProjectId(undefined);
                setFolderId(undefined);
              }}
            >
              {(workspaces.data ?? []).map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="files-project">Project</label>
            <select
              id="files-project"
              className="input"
              value={activeProjectId ?? ""}
              onChange={(event) => {
                setProjectId(event.target.value);
                setFolderId(undefined);
              }}
              disabled={!activeWorkspaceId || projects.isPending}
            >
              {(projects.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="files-folder">Folder</label>
            <select
              id="files-folder"
              className="input"
              value={folderId ?? ""}
              onChange={(event) =>
                setFolderId(event.target.value || undefined)
              }
              disabled={!activeProjectId || folders.isPending}
            >
              <option value="">Project root</option>
              {(folders.data ?? []).map((folder) => (
                <option key={folder.id} value={folder.id}>
                  {folder.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card pad">
          <h3>Upload</h3>
          <p className="muted small" style={{ marginTop: 4 }}>
            Upload a real file to the selected project folder.
          </p>

          <input
            ref={inputRef}
            type="file"
            style={{ marginTop: 14, width: "100%" }}
            disabled={!activeProjectId || upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.currentTarget.value = "";
            }}
          />

          <button
            className="btn primary"
            type="button"
            style={{ marginTop: 12 }}
            disabled={!activeProjectId || upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            {upload.isPending ? "Uploading…" : "Choose file"}
          </button>
        </div>

        <div className="card pad">
          <h3>New folder</h3>
          <p className="muted small" style={{ marginTop: 4 }}>
            Create a persistent folder under the current project location.
          </p>

          <div className="field" style={{ marginTop: 14 }}>
            <label htmlFor="new-folder-name">Folder name</label>
            <input
              id="new-folder-name"
              className="input"
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              placeholder="e.g. raw data"
              disabled={!activeProjectId || createFolder.isPending}
            />
          </div>

          <button
            className="btn"
            type="button"
            style={{ marginTop: 12 }}
            disabled={
              !activeProjectId ||
              folderName.trim().length < 1 ||
              createFolder.isPending
            }
            onClick={() => createFolder.mutate()}
          >
            {createFolder.isPending ? "Creating…" : "Create folder"}
          </button>
        </div>
      </section>

      <section className="card table-wrap">
        <div className="row" style={{ padding: "0 16px 12px" }}>
          <div>
            <h3>Project files</h3>
            <div className="muted small">
              {files.data?.total ?? 0} file
              {(files.data?.total ?? 0) === 1 ? "" : "s"}
            </div>
          </div>
        </div>

        <table className="table">
          <thead>
            <tr>
              <th>File</th>
              <th>Kind</th>
              <th>Size</th>
              <th>Status</th>
              <th>Extraction</th>
              <th>Move</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(files.data?.items ?? []).map((file) => (
              <tr key={file.id}>
                <td>
                  <div className="strong">{file.original_filename}</div>
                  <div className="meta">
                    {new Date(file.created_at).toLocaleString()}
                  </div>
                </td>
                <td>{file.file_kind}</td>
                <td>{formatBytes(file.size_bytes)}</td>
                <td><span className="tag">{file.status}</span></td>
                <td>
                  <span className="tag">{file.extraction_status}</span>
                </td>
                <td>
                  <span className="tag">
                    {evidenceLabel(evidenceByFileId.get(file.id))}
                  </span>
                </td>
                <td>
                  <select
                    className="input"
                    aria-label={"Move " + file.original_filename}
                    defaultValue=""
                    disabled={move.isPending}
                    onChange={(event) => {
                      const target = event.target.value;
                      event.currentTarget.value = "";
                      void move.mutateAsync({
                        fileId: file.id,
                        folderId: target || undefined,
                      });
                    }}
                  >
                    <option value="">Select destination</option>
                    <option value="">Project root</option>
                    {(folders.data ?? []).map((folder) => (
                      <option key={folder.id} value={folder.id}>
                        {folder.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <div className="actions">
                    <a
                      className="btn ghost"
                      href={projectFileContentUrl(file.id)}
                    >
                      Download
                    </a>
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(file.id)}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {!files.isPending && (files.data?.items.length ?? 0) === 0 && (
          <div className="empty" style={{ margin: 16 }}>
            <div className="big">∅</div>
            <div>No files exist in this project location yet.</div>
          </div>
        )}
      </section>

      {!activeProjectId && (
        <section className="card pad empty">
          <div className="big">∅</div>
          <div>
            Create a project in Workspace before uploading files.
          </div>
          <Link className="btn" href="/workspace" style={{ marginTop: 12 }}>
            Open workspace
          </Link>
        </section>
      )}
    </div>
  );
}