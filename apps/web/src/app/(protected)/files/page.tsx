"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/app-shell";

export default function FilesPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");
  const [folderId, setFolderId] = useState("");
  const [folderName, setFolderName] = useState("");
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const projects = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.projects(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (!projectId && projects.data?.items[0]?.id) {
      setProjectId(projects.data.items[0].id);
    }
  }, [projects.data, projectId]);

  const files = useQuery({
    queryKey: ["files", projectId],
    queryFn: () => api.files(projectId),
    enabled: !!projectId,
  });

  const folders = useQuery({
    queryKey: ["folders", projectId],
    queryFn: () => api.folders(projectId),
    enabled: !!projectId,
  });

  const upload = useMutation({
    mutationFn: () => {
      if (!selectedFile) {
        throw new Error("Select a file first.");
      }

      return api.uploadFile(
        projectId,
        selectedFile,
        folderId || null,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["files", projectId],
      });

      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
  });

  const createFolder = useMutation({
    mutationFn: () =>
      api.createFolder(projectId, {
        name: folderName.trim(),
        parent_id: folderId || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["folders", projectId],
      });

      setFolderName("");
    },
  });

  const move = useMutation({
    mutationFn: ({
      fileId,
      nextFolderId,
    }: {
      fileId: string;
      nextFolderId: string | null;
    }) =>
      api.moveFile(
        fileId,
        nextFolderId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["files", projectId],
      });
    },
  });

  const remove = useMutation({
    mutationFn: (fileId: string) =>
      api.deleteFile(fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["files", projectId],
      });
    },
  });

  const download = useMutation({
    mutationFn: (fileId: string) =>
      api.downloadFile(fileId),
    onSuccess: (blob, fileId) => {
      const url =
        URL.createObjectURL(blob);

      const anchor =
        document.createElement("a");

      anchor.href = url;
      anchor.download =
        files.data?.items.find(
          (file) => file.id === fileId,
        )?.original_filename ??
        "download";

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      URL.revokeObjectURL(url);
    },
  });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Project storage
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Files
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Uploads, folders, lifecycle state, extraction
          status, downloads, moves, and deletion are
          connected to the project file APIs.
        </p>
      </header>

      <section className="card p-5">
        <div className="muted text-sm">
          Project
        </div>

        <select
          className="input mt-2 min-w-72"
          value={projectId}
          onChange={(event) =>
            setProjectId(event.target.value)
          }
        >
          {(projects.data?.items ?? []).map(
            (project) => (
              <option
                key={project.id}
                value={project.id}
              >
                {project.name}
              </option>
            ),
          )}
        </select>
      </section>

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="card p-5">
          <h2 className="font-semibold">
            Upload file
          </h2>

          <input
            ref={fileInputRef}
            className="input mt-4"
            type="file"
            onChange={(event) =>
              setSelectedFile(
                event.target.files?.[0] ??
                  null,
              )
            }
          />

          <select
            className="input mt-3"
            value={folderId}
            onChange={(event) =>
              setFolderId(event.target.value)
            }
          >
            <option value="">
              Project root
            </option>

            {(folders.data?.items ?? []).map(
              (folder) => (
                <option
                  key={folder.id}
                  value={folder.id}
                >
                  {folder.name}
                </option>
              ),
            )}
          </select>

          <button
            className="btn btn-primary mt-4"
            disabled={
              !projectId ||
              !selectedFile ||
              upload.isPending
            }
            onClick={() =>
              upload.mutate()
            }
          >
            {upload.isPending
              ? "Uploading…"
              : "Upload"}
          </button>

          {selectedFile && (
            <div className="muted text-sm mt-3">
              Selected:{" "}
              {selectedFile.name}
            </div>
          )}

          {upload.error && (
            <div
              className="text-sm mt-3"
              style={{
                color: "var(--danger)",
              }}
            >
              {upload.error.message}
            </div>
          )}
        </section>

        <section className="card p-5">
          <h2 className="font-semibold">
            Folders
          </h2>

          <div className="flex gap-2 mt-4">
            <input
              className="input"
              placeholder="New folder name"
              value={folderName}
              onChange={(event) =>
                setFolderName(
                  event.target.value,
                )
              }
            />

            <button
              className="btn btn-secondary"
              disabled={
                !projectId ||
                !folderName.trim() ||
                createFolder.isPending
              }
              onClick={() =>
                createFolder.mutate()
              }
            >
              {createFolder.isPending
                ? "Creating…"
                : "Create"}
            </button>
          </div>

          <div className="mt-5 space-y-2">
            {(folders.data?.items ?? []).map(
              (folder) => (
                <div
                  key={folder.id}
                  className="rounded-xl border p-3 text-sm"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="font-medium">
                    {folder.name}
                  </div>

                  <div className="muted text-xs mt-1">
                    {folder.parent_id
                      ? "Nested folder"
                      : "Project root folder"}
                  </div>
                </div>
              ),
            )}

            {!folders.isPending &&
              !folders.data?.items.length && (
                <div className="muted text-sm">
                  No folders yet.
                </div>
              )}
          </div>

          {createFolder.error && (
            <div
              className="text-sm mt-3"
              style={{
                color: "var(--danger)",
              }}
            >
              {createFolder.error.message}
            </div>
          )}
        </section>
      </div>

      <section className="card overflow-hidden">
        <div
          className="px-5 py-4 border-b"
          style={{
            borderColor: "var(--line)",
          }}
        >
          <div className="font-semibold">
            Project files
          </div>

          <div className="muted text-xs mt-1">
            {files.data?.total ?? 0} files
          </div>
        </div>

        <div className="divide-y">
          {files.isPending && (
            <div className="p-6 muted">
              Loading files…
            </div>
          )}

          {!files.isPending &&
            !files.data?.items.length && (
              <div className="p-8 muted text-sm">
                No files are available for this
                project.
              </div>
            )}

          {(files.data?.items ?? []).map(
            (file) => (
              <div
                key={file.id}
                className="p-5"
              >
                <div className="flex flex-wrap justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium break-all">
                      {file.original_filename}
                    </div>

                    <div className="muted text-sm mt-1">
                      {formatBytes(
                        file.size_bytes,
                      )}{" "}
                      · {file.file_kind} ·{" "}
                      {file.status}
                    </div>

                    <div className="muted text-xs mt-1">
                      Extraction:{" "}
                      {file.extraction_status}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      className="btn btn-secondary text-sm"
                      disabled={
                        download.isPending
                      }
                      onClick={() =>
                        download.mutate(
                          file.id,
                        )
                      }
                    >
                      {download.isPending
                        ? "Downloading…"
                        : "Download"}
                    </button>

                    <button
                      className="btn btn-secondary text-sm"
                      disabled={
                        remove.isPending
                      }
                      onClick={() => {
                        if (
                          window.confirm(
                            `Delete "${file.original_filename}"?`,
                          )
                        ) {
                          remove.mutate(
                            file.id,
                          );
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div className="mt-4">
                  <label className="muted text-xs">
                    Folder
                  </label>

                  <select
                    className="input mt-1"
                    value={""}
                    onChange={(event) => {
                      move.mutate({
                        fileId: file.id,
                        nextFolderId:
                          event.target.value ||
                          null,
                      });
                    }}
                  >
                    <option value="">
                      Select destination…
                    </option>

                    <option value="">
                      Project root
                    </option>

                    {(folders.data?.items ??
                      []).map(
                      (folder) => (
                        <option
                          key={folder.id}
                          value={folder.id}
                        >
                          {folder.name}
                        </option>
                      ),
                    )}
                  </select>
                </div>
              </div>
            ),
          )}
        </div>

        {download.error && (
          <div
            className="px-5 pb-5 text-sm"
            style={{
              color: "var(--danger)",
            }}
          >
            {download.error.message}
          </div>
        )}

        {move.error && (
          <div
            className="px-5 pb-5 text-sm"
            style={{
              color: "var(--danger)",
            }}
          >
            {move.error.message}
          </div>
        )}

        {remove.error && (
          <div
            className="px-5 pb-5 text-sm"
            style={{
              color: "var(--danger)",
            }}
          >
            {remove.error.message}
          </div>
        )}
      </section>
    </div>
  );
}

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  if (value < 1024 * 1024 * 1024) {
    return `${(
      value /
      (1024 * 1024)
    ).toFixed(1)} MB`;
  }

  return `${(
    value /
    (1024 * 1024 * 1024)
  ).toFixed(1)} GB`;
}