"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { useResearchContext } from "@/lib/research-context";
import { queryKeys } from "@/lib/query-keys";
import FileIntelligencePanel from "@/components/FileIntelligencePanel";
import {
  createProjectFolder,
  deleteProjectFile,
  listProjectFiles,
  listProjectFolders,
  moveProjectFile,
  projectFileContentUrl,
  renameProjectFolder,
  uploadProjectFile,
} from "@/lib/api/files";
import {
  getProjectFileEvidence,
  type ProjectFileEvidence,
} from "@/lib/api/project-file-evidence";

function evidenceLabel(item: ProjectFileEvidence | undefined): string {
  if (!item) return "Not evaluated";
  if (item.evidence_status === "synced") return "Synced · " + item.chunk_count + " chunks";
  if (item.evidence_status === "awaiting_report") return "Waiting for report";
  if (item.evidence_status === "unavailable") return "Unavailable";
  return "Processing";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

export default function FilesWorkspace() {
  const [folderId, setFolderId] = useState<string>();
  const [folderName, setFolderName] = useState("");
  const [folderRenameId, setFolderRenameId] = useState<string>();
  const [folderRenameName, setFolderRenameName] = useState("");
  const [selectedFileId, setSelectedFileId] = useState<string>();
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileFilter, setFileFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const {
    workspaceId,
    projectId,
    workspacesQuery,
    projectsQuery,
    setWorkspace,
    setProject,
  } = useResearchContext();

  const activeProjectId = projectId ?? undefined;
  const activeWorkspaceId = workspaceId ?? undefined;

  const folders = useQuery({
    queryKey: queryKeys.projectFolders(activeProjectId ?? null),
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listProjectFolders(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });

  const files = useQuery({
    queryKey: queryKeys.projectFiles(activeProjectId ?? null, folderId ?? null),
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return listProjectFiles(activeProjectId, folderId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 10_000,
  });

  const evidence = useQuery({
    queryKey: queryKeys.projectFileEvidence(activeProjectId ?? null),
    queryFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      return getProjectFileEvidence(activeProjectId);
    },
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });

  const createFolder = useMutation({
    mutationFn: () => {
      if (!activeProjectId) throw new Error("No project is selected.");
      const name = folderName.trim();
      if (!name) throw new Error("Folder name is required.");
      return createProjectFolder(activeProjectId, name, folderId);
    },
    onSuccess: async () => {
      setFolderName("");
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projectFolders(activeProjectId ?? null),
      });
    },
  });

  const renameFolder = useMutation({
    mutationFn: () => {
      if (!activeProjectId || !folderRenameId) throw new Error("No folder is selected.");
      const name = folderRenameName.trim();
      if (!name) throw new Error("Folder name is required.");
      return renameProjectFolder(activeProjectId, folderRenameId, name);
    },
    onSuccess: async () => {
      setFolderRenameId(undefined);
      setFolderRenameName("");
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projectFolders(activeProjectId ?? null),
      });
    },
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      if (!activeProjectId) throw new Error("No project is selected.");
      if (!file.name.trim()) throw new Error("The selected file has no filename.");
      if (file.size === 0) throw new Error("Empty files cannot be uploaded.");
      if (file.name.length > 255) throw new Error("The filename is too long.");
      setUploadProgress(0);
      return uploadProjectFile(
        activeProjectId,
        file,
        folderId,
        setUploadProgress,
      );
    },
    onSuccess: async () => {
      setUploadProgress(100);
      await queryClient.invalidateQueries({
        queryKey: ["project-files", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projectFileEvidence(activeProjectId ?? null),
      });
    },
    onError: () => setUploadProgress(0),
  });

  const move = useMutation({
    mutationFn: ({
      fileId,
      destinationFolderId,
    }: {
      fileId: string;
      destinationFolderId?: string;
    }) => moveProjectFile(fileId, destinationFolderId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["project-files", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projectFileEvidence(activeProjectId ?? null),
      });
    },
  });

  const remove = useMutation({
    mutationFn: (fileId: string) => deleteProjectFile(fileId),
    onSuccess: async (_data, fileId) => {
      if (selectedFileId === fileId) setSelectedFileId(undefined);
      await queryClient.invalidateQueries({
        queryKey: ["project-files", activeProjectId],
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.projectFileEvidence(activeProjectId ?? null),
      });
    },
  });

  const evidenceByFileId = useMemo(
    () => new Map((evidence.data?.items ?? []).map((item) => [item.file_id, item])),
    [evidence.data?.items],
  );

  const filteredFiles = useMemo(() => {
    const normalized = fileFilter.trim().toLowerCase();
    return (files.data?.items ?? []).filter((file) => {
      const matchesName =
        !normalized ||
        file.original_filename.toLowerCase().includes(normalized) ||
        file.file_kind.toLowerCase().includes(normalized);
      const matchesKind = !kindFilter || file.file_kind === kindFilter;
      const matchesStatus = !statusFilter || file.status === statusFilter;
      return matchesName && matchesKind && matchesStatus;
    });
  }, [fileFilter, files.data?.items, kindFilter, statusFilter]);

  const errors = [
    workspacesQuery.error,
    projectsQuery.error,
    folders.error,
    files.error,
    evidence.error,
  ].filter(Boolean);

  if (errors.length) {
    const error = errors[0];
    return (
      <section className="card pad" role="alert">
        <h2>Files unavailable</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          {error instanceof Error ? error.message : "Unable to load project files."}
        </p>
        <button
          className="btn"
          type="button"
          style={{ marginTop: 14 }}
          onClick={() => {
            void workspacesQuery.refetch();
            void projectsQuery.refetch();
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

  if (!activeProjectId) {
    return (
      <section className="card pad empty">
        <div className="big">∅</div>
        <h2>Select a research project</h2>
        <p className="muted">
          Files and intelligence are project-scoped. Select a project before uploading or analyzing files.
        </p>
        <Link className="btn primary" href="/workspace" style={{ marginTop: 12 }}>
          Open workspace
        </Link>
      </section>
    );
  }

  const selectedFile = (files.data?.items ?? []).find(
    (file) => file.id === selectedFileId,
  );

  const folderOptions = folders.data ?? [];

  return (
    <div className="stack" style={{ gap: 16 }}>
      <section className="card pad">
        <div className="row">
          <div>
            <div className="eyebrow">Project files</div>
            <h2 style={{ marginTop: 4 }}>Files & intelligence</h2>
            <p className="muted small" style={{ marginTop: 4 }}>
              Persistent project storage with extraction, evidence and file-specific intelligence.
            </p>
          </div>
          <span className="tag success">Live</span>
        </div>

        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="files-workspace">Workspace</label>
            <select
              id="files-workspace"
              className="input"
              value={activeWorkspaceId ?? ""}
              onChange={(event) => {
                setWorkspace(event.target.value);
                setFolderId(undefined);
                setSelectedFileId(undefined);
              }}
            >
              {(workspacesQuery.data ?? []).map((workspace) => (
                <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
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
                setProject(event.target.value);
                setFolderId(undefined);
                setSelectedFileId(undefined);
              }}
              disabled={!activeWorkspaceId || projectsQuery.isPending}
            >
              {(projectsQuery.data ?? []).map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="files-folder">Folder</label>
            <select
              id="files-folder"
              className="input"
              value={folderId ?? ""}
              onChange={(event) => {
                setFolderId(event.target.value || undefined);
                setSelectedFileId(undefined);
              }}
              disabled={!activeProjectId || folders.isPending}
            >
              <option value="">Project root</option>
              {folderOptions.map((folder) => (
                <option key={folder.id} value={folder.id}>{folder.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-3" style={{ marginTop: 12 }}>
          <div className="field">
            <label htmlFor="files-filter">Filter</label>
            <input
              id="files-filter"
              className="input"
              value={fileFilter}
              onChange={(event) => setFileFilter(event.target.value)}
              placeholder="Filename or kind"
            />
          </div>
          <div className="field">
            <label htmlFor="files-kind">Kind</label>
            <select
              id="files-kind"
              className="input"
              value={kindFilter}
              onChange={(event) => setKindFilter(event.target.value)}
            >
              <option value="">All kinds</option>
              <option value="document">Document</option>
              <option value="pdf">PDF</option>
              <option value="text">Text</option>
              <option value="code">Code</option>
              <option value="structured_data">Structured data</option>
              <option value="spreadsheet">Spreadsheet</option>
              <option value="image">Image</option>
              <option value="archive">Archive</option>
              <option value="presentation">Presentation</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="files-status">Status</label>
            <select
              id="files-status"
              className="input"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="uploaded">Uploaded</option>
              <option value="processing">Processing</option>
              <option value="ready">Ready</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
      </section>

      <section className="grid grid-2">
        <div className="card pad">
          <h3>Upload</h3>
          <p className="muted small" style={{ marginTop: 4 }}>
            Files are uploaded to the current project and folder. The request is streamed through the application API.
          </p>
          <input
            ref={inputRef}
            type="file"
            style={{ marginTop: 14, width: "100%" }}
            disabled={upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.currentTarget.value = "";
            }}
          />
          {upload.isPending && (
            <div style={{ marginTop: 12 }} aria-live="polite">
              <div className="row small"><span>Upload progress</span><b>{uploadProgress}%</b></div>
              <div className="progress" style={{ marginTop: 7 }}>
                <span style={{ width: uploadProgress + "%" }} />
              </div>
            </div>
          )}
          <button
            className="btn primary"
            type="button"
            style={{ marginTop: 12 }}
            disabled={upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            {upload.isPending ? "Uploading…" : "Choose file"}
          </button>
          {upload.error instanceof Error && (
            <p className="muted small" role="alert" style={{ marginTop: 8 }}>
              {upload.error.message}
            </p>
          )}
        </div>

        <div className="card pad">
          <h3>Folders</h3>
          <p className="muted small" style={{ marginTop: 4 }}>
            Create nested folders and rename existing project folders.
          </p>
          <div className="field" style={{ marginTop: 14 }}>
            <label htmlFor="new-folder-name">New folder name</label>
            <input
              id="new-folder-name"
              className="input"
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              placeholder="e.g. raw data"
              disabled={createFolder.isPending}
            />
          </div>
          <button
            className="btn"
            type="button"
            style={{ marginTop: 10 }}
            disabled={!folderName.trim() || createFolder.isPending}
            onClick={() => createFolder.mutate()}
          >
            {createFolder.isPending ? "Creating…" : "Create folder"}
          </button>

          {folderOptions.length > 0 && (
            <div style={{ marginTop: 18 }}>
              <div className="field">
                <label htmlFor="rename-folder">Rename folder</label>
                <select
                  id="rename-folder"
                  className="input"
                  value={folderRenameId ?? ""}
                  onChange={(event) => {
                    const id = event.target.value || undefined;
                    const folder = folderOptions.find((item) => item.id === id);
                    setFolderRenameId(id);
                    setFolderRenameName(folder?.name ?? "");
                  }}
                  disabled={renameFolder.isPending}
                >
                  <option value="">Select folder</option>
                  {folderOptions.map((folder) => (
                    <option key={folder.id} value={folder.id}>{folder.name}</option>
                  ))}
                </select>
              </div>
              {folderRenameId && (
                <div className="actions" style={{ marginTop: 8 }}>
                  <input
                    className="input"
                    value={folderRenameName}
                    onChange={(event) => setFolderRenameName(event.target.value)}
                    aria-label="Renamed folder name"
                  />
                  <button
                    className="btn ghost"
                    type="button"
                    disabled={!folderRenameName.trim() || renameFolder.isPending}
                    onClick={() => renameFolder.mutate()}
                  >
                    {renameFolder.isPending ? "Saving…" : "Rename"}
                  </button>
                </div>
              )}
            </div>
          )}

          {(createFolder.error instanceof Error || renameFolder.error instanceof Error) && (
            <p className="muted small" role="alert" style={{ marginTop: 8 }}>
              {(createFolder.error ?? renameFolder.error)?.message}
            </p>
          )}
        </div>
      </section>

      <section className="card table-wrap">
        <div className="row" style={{ padding: "0 16px 12px" }}>
          <div>
            <h3>Project files</h3>
            <div className="muted small">
              {filteredFiles.length} shown · {files.data?.total ?? 0} in current folder
            </div>
          </div>
          <button
            className="btn ghost"
            type="button"
            onClick={() => void files.refetch()}
            disabled={files.isFetching}
          >
            {files.isFetching ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        <table className="table">
          <thead>
            <tr>
              <th>File</th>
              <th>Kind</th>
              <th>Size</th>
              <th>Status</th>
              <th>Extraction</th>
              <th>Evidence</th>
              <th>Move</th>
              <th>Intelligence</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filteredFiles.map((file) => (
              <tr key={file.id}>
                <td>
                  <div className="strong">{file.original_filename}</div>
                  <div className="meta">{new Date(file.created_at).toLocaleString()}</div>
                </td>
                <td><span className="tag">{file.file_kind}</span></td>
                <td>{formatBytes(file.size_bytes)}</td>
                <td><span className="tag">{file.status}</span></td>
                <td><span className="tag">{file.extraction_status}</span></td>
                <td><span className="tag">{evidenceLabel(evidenceByFileId.get(file.id))}</span></td>
                <td>
                  <select
                    className="input"
                    aria-label={"Move " + file.original_filename}
                    defaultValue=""
                    disabled={move.isPending}
                    onChange={(event) => {
                      const target = event.target.value;
                      event.currentTarget.value = "";
                      move.mutate({
                        fileId: file.id,
                        destinationFolderId: target === "__root__" ? undefined : target || undefined,
                      });
                    }}
                  >
                    <option value="">Select destination</option>
                    <option value="__root__">Project root</option>
                    {folderOptions.map((folder) => (
                      <option key={folder.id} value={folder.id}>{folder.name}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    className="btn ghost"
                    type="button"
                    aria-label={"Inspect " + file.original_filename}
                    onClick={() => setSelectedFileId(file.id)}
                  >
                    {selectedFileId === file.id ? "Selected" : "Inspect"}
                  </button>
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

        {!files.isPending && filteredFiles.length === 0 && (
          <div className="empty" style={{ margin: 16 }}>
            <div className="big">∅</div>
            <div>{fileFilter || kindFilter || statusFilter ? "No files match the current filters." : "No files exist in this project location yet."}</div>
          </div>
        )}
      </section>

      {selectedFile && (
        <section>
          <div className="row" style={{ marginBottom: 8 }}>
            <div>
              <div className="eyebrow">File intelligence</div>
              <h2 style={{ marginTop: 4 }}>{selectedFile.original_filename}</h2>
            </div>
            <button
              className="btn ghost"
              type="button"
              onClick={() => setSelectedFileId(undefined)}
            >
              Close
            </button>
          </div>
          <FileIntelligencePanel
            fileId={selectedFile.id}
            filename={selectedFile.original_filename}
            fileKind={selectedFile.file_kind}
          />
        </section>
      )}
    </div>
  );
}
