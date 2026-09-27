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
import type { components } from "@/lib/api/generated";

type Schema = components["schemas"];


export default function CollaborationPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState("");
  const [reportId, setReportId] = useState("");

  const [memberUserId, setMemberUserId] =
    useState("");
  const [memberRole, setMemberRole] =
    useState("member");

  const [branchName, setBranchName] =
    useState("");

  const [commentBody, setCommentBody] =
    useState("");

  const [taskTitle, setTaskTitle] =
    useState("");
  const [taskDescription, setTaskDescription] =
    useState("");
  const [taskSeverity, setTaskSeverity] =
    useState("info");
  const [taskAssignee, setTaskAssignee] =
    useState("");

  const projects = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.projects(workspaceId!),
    enabled: !!workspaceId,
  });

  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: () => api.reports(workspaceId!),
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (
      !projectId &&
      projects.data?.items[0]?.id
    ) {
      setProjectId(
        projects.data.items[0].id,
      );
    }
  }, [projects.data, projectId]);

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

  const projectMembers = useQuery({
    queryKey: [
      "project-members",
      projectId,
    ],
    queryFn: () =>
      api.projectMembers(projectId),
    enabled: !!projectId,
  });

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

  const manuscriptId =
    manuscript.data?.manuscript.id ?? "";

  const versionId =
    manuscript.data?.version.id ?? "";

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

  const branches = useQuery({
    queryKey: [
      "manuscript-branches",
      reportId,
      manuscriptId,
    ],
    queryFn: () =>
      api.branches(
        reportId,
        manuscriptId,
      ),
    enabled:
      !!reportId &&
      !!manuscriptId,
    retry: false,
  });

  const branchItems =
    branches.data?.items ?? [];

  const comments = useQuery({
    queryKey: [
      "manuscript-comments",
      reportId,
      versionId,
    ],
    queryFn: () =>
      api.comments(
        reportId,
        versionId,
      ),
    enabled:
      !!reportId &&
      !!versionId,
    retry: false,
  });

  const reviewTasks = useQuery({
    queryKey: [
      "manuscript-review-tasks",
      reportId,
      versionId,
    ],
    queryFn: () =>
      api.reviewTasks(
        reportId,
        versionId,
      ),
    enabled:
      !!reportId &&
      !!versionId,
    retry: false,
  });

  const addMember = useMutation({
    mutationFn: () =>
      api.addProjectMember(
        projectId,
        {
          user_id:
            memberUserId.trim(),
          role: memberRole,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "project-members",
          projectId,
        ],
      });

      setMemberUserId("");
    },
  });

  const changeRole = useMutation({
    mutationFn: ({
      memberId,
      role,
    }: {
      memberId: string;
      role: string;
    }) =>
      api.changeProjectMemberRole(
        projectId,
        memberId,
        role,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "project-members",
          projectId,
        ],
      });
    },
  });

  const removeMember = useMutation({
    mutationFn: (memberId: string) =>
      api.removeProjectMember(
        projectId,
        memberId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "project-members",
          projectId,
        ],
      });
    },
  });

  const createBranch = useMutation({
    mutationFn: () =>
      api.createBranch(reportId, {
        manuscript_id: manuscriptId,
        name: branchName.trim(),
        head_version_id: versionId,
        is_default: false,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-branches",
          reportId,
          manuscriptId,
        ],
      });

      setBranchName("");
    },
  });

  const createComment = useMutation({
    mutationFn: () =>
      api.createComment(
        reportId,
        versionId,
        {
          body: commentBody.trim(),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-comments",
          reportId,
          versionId,
        ],
      });

      setCommentBody("");
    },
  });

  const resolveComment = useMutation({
    mutationFn: (commentId: string) =>
      api.resolveComment(
        reportId,
        commentId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-comments",
          reportId,
          versionId,
        ],
      });
    },
  });

  const reopenComment = useMutation({
    mutationFn: (commentId: string) =>
      api.reopenComment(
        reportId,
        commentId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-comments",
          reportId,
          versionId,
        ],
      });
    },
  });

  const createTask = useMutation({
    mutationFn: () =>
      api.createReviewTask(
        reportId,
        versionId,
        {
          manuscript_version_id:
            versionId,
          title:
            taskTitle.trim(),
          description:
            taskDescription.trim() ||
            null,
          severity: taskSeverity,
          assignee_user_id:
            taskAssignee.trim() ||
            null,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "manuscript-review-tasks",
          reportId,
          versionId,
        ],
      });

      setTaskTitle("");
      setTaskDescription("");
      setTaskAssignee("");
    },
  });

  const changeTaskStatus =
    useMutation({
      mutationFn: ({
        taskId,
        status,
      }: {
        taskId: string;
        status: string;
      }) =>
        api.changeReviewTaskStatus(
          reportId,
          taskId,
          status,
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: [
            "manuscript-review-tasks",
            reportId,
            versionId,
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

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Team collaboration
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Collaboration
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Project membership, manuscript versions,
          branches, comments, and review tasks are
          backed directly by the collaboration APIs.
        </p>
      </header>

      <section className="card p-5">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <div className="muted text-sm">
              Project
            </div>

            <select
              className="input mt-2"
              value={projectId}
              onChange={(event) =>
                setProjectId(
                  event.target.value,
                )
              }
            >
              {(
                projects.data?.items ??
                []
              ).map((project) => (
                <option
                  key={project.id}
                  value={project.id}
                >
                  {project.name}
                </option>
              ))}
            </select>
          </div>

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
        </div>
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h2 className="font-semibold">
              Project members
            </h2>

            <p className="muted text-sm mt-1">
              Membership is enforced by the backend
              project authorization boundary.
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-3 mt-5">
          <input
            className="input md:col-span-2"
            placeholder="User UUID"
            value={memberUserId}
            onChange={(event) =>
              setMemberUserId(
                event.target.value,
              )
            }
          />

          <select
            className="input"
            value={memberRole}
            onChange={(event) =>
              setMemberRole(
                event.target.value,
              )
            }
          >
            <option value="owner">
              owner
            </option>
            <option value="admin">
              admin
            </option>
            <option value="member">
              member
            </option>
            <option value="viewer">
              viewer
            </option>
          </select>
        </div>

        <button
          className="btn btn-primary mt-3"
          disabled={
            !projectId ||
            !memberUserId.trim() ||
            addMember.isPending
          }
          onClick={() =>
            addMember.mutate()
          }
        >
          {addMember.isPending
            ? "Adding…"
            : "Add member"}
        </button>

        {addMember.error && (
          <ErrorMessage
            message={addMember.error.message}
          />
        )}

        <div className="mt-6 divide-y">
          {projectMembers.isPending && (
            <div className="py-5 muted">
              Loading members…
            </div>
          )}

          {(
            projectMembers.data?.items ??
            []
          ).map((member) => (
            <div
              key={member.id}
              className="py-4 flex flex-wrap items-center justify-between gap-4"
            >
              <div>
                <div className="font-medium break-all">
                  {member.user_id}
                </div>

                <div className="muted text-xs mt-1 break-all">
                  membership {member.id}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <select
                  className="input !w-auto text-sm"
                  value={member.role}
                  onChange={(event) =>
                    changeRole.mutate({
                      memberId:
                        member.id,
                      role:
                        event.target
                          .value,
                    })
                  }
                >
                  <option value="owner">
                    owner
                  </option>
                  <option value="admin">
                    admin
                  </option>
                  <option value="member">
                    member
                  </option>
                  <option value="viewer">
                    viewer
                  </option>
                </select>

                <button
                  className="btn btn-secondary text-sm"
                  disabled={
                    removeMember.isPending
                  }
                  onClick={() => {
                    if (
                      window.confirm(
                        "Remove this project member?",
                      )
                    ) {
                      removeMember.mutate(
                        member.id,
                      );
                    }
                  }}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}

          {!projectMembers.isPending &&
            !projectMembers.data
              ?.items.length && (
              <div className="py-6 muted text-sm">
                No project members returned.
              </div>
            )}
        </div>
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h2 className="font-semibold">
              Manuscript collaboration
            </h2>

            {manuscript.data ? (
              <p className="muted text-sm mt-1">
                Current version v
                {
                  manuscript.data
                    .version.version
                }{" "}
                ·{" "}
                {
                  manuscript.data
                    .version.status
                }
              </p>
            ) : (
              <p className="muted text-sm mt-1">
                No current manuscript is available
                for this report.
              </p>
            )}
          </div>
        </div>

        {manuscript.error && (
          <div className="muted text-sm mt-4">
            Manuscript unavailable:{" "}
            {manuscript.error.message}
          </div>
        )}

        {manuscript.data && (
          <>
            <div className="grid md:grid-cols-3 gap-4 mt-5">
              <Metric
                label="Sections"
                value={
                  manuscript.data
                    .sections.length
                }
              />

              <Metric
                label="Versions"
                value={
                  versions.data
                    ?.total ?? "—"
                }
              />

              <Metric
                label="Branches"
                value={
                  branches.data
                    ?.total ?? "—"
                }
              />
            </div>

            <div className="grid lg:grid-cols-2 gap-5 mt-5">
              <div>
                <h3 className="font-medium">
                  Version history
                </h3>

                <div className="mt-3 space-y-2">
                  {(
                    versions.data
                      ?.items ?? []
                  ).map((version) => (
                    <div
                      key={version.id}
                      className="rounded-xl border p-3"
                      style={{
                        borderColor:
                          "var(--line)",
                      }}
                    >
                      <div className="flex justify-between gap-3">
                        <span className="font-medium">
                          v{version.version}
                        </span>

                        <span className="muted text-xs">
                          {version.status}
                        </span>
                      </div>

                      <div className="muted text-xs mt-2">
                        {version.title} ·{" "}
                        {
                          version.word_target
                        }{" "}
                        words
                      </div>

                      <div className="muted text-xs mt-1 break-all">
                        {version.id}
                      </div>
                    </div>
                  ))}

                  {!versions.isPending &&
                    !versions.data
                      ?.items.length && (
                      <div className="muted text-sm">
                        No versions returned.
                      </div>
                    )}
                </div>
              </div>

              <div>
                <h3 className="font-medium">
                  Branches
                </h3>

                <div className="flex gap-2 mt-3">
                  <input
                    className="input"
                    placeholder="New branch name"
                    value={branchName}
                    onChange={(event) =>
                      setBranchName(
                        event.target
                          .value,
                      )
                    }
                  />

                  <button
                    className="btn btn-secondary"
                    disabled={
                      !branchName.trim() ||
                      !versionId ||
                      !manuscriptId ||
                      createBranch.isPending
                    }
                    onClick={() =>
                      createBranch.mutate()
                    }
                  >
                    {createBranch.isPending
                      ? "Creating…"
                      : "Create"}
                  </button>
                </div>

                {createBranch.error && (
                  <ErrorMessage
                    message={
                      createBranch.error
                        .message
                    }
                  />
                )}

                <div className="mt-3 space-y-2">
                  {branchItems.map(
                    (branch) => (
                      <div
                        key={branch.id}
                        className="rounded-xl border p-3"
                        style={{
                          borderColor:
                            "var(--line)",
                        }}
                      >
                        <div className="flex justify-between gap-3">
                          <span className="font-medium">
                            {branch.name}
                          </span>

                          {branch.is_default && (
                            <span className="muted text-xs">
                              default
                            </span>
                          )}
                        </div>

                        <div className="muted text-xs mt-2 break-all">
                          Head:{" "}
                          {
                            branch.head_version_id
                          }
                        </div>
                      </div>
                    ),
                  )}

                  {!branches.isPending &&
                    !branchItems.length && (
                      <div className="muted text-sm">
                        No branches returned.
                      </div>
                    )}
                </div>
              </div>
            </div>
          </>
        )}
      </section>

      {versionId && (
        <div className="grid lg:grid-cols-2 gap-5">
          <section className="card p-5">
            <h2 className="font-semibold">
              Comments
            </h2>

            <textarea
              className="input mt-4 min-h-28 resize-y"
              placeholder="Add a manuscript comment…"
              value={commentBody}
              onChange={(event) =>
                setCommentBody(
                  event.target.value,
                )
              }
            />

            <button
              className="btn btn-primary mt-3"
              disabled={
                !commentBody.trim() ||
                createComment.isPending
              }
              onClick={() =>
                createComment.mutate()
              }
            >
              {createComment.isPending
                ? "Posting…"
                : "Add comment"}
            </button>

            {createComment.error && (
              <ErrorMessage
                message={
                  createComment.error
                    .message
                }
              />
            )}

            <div className="mt-5 space-y-3">
              {comments.isPending && (
                <div className="muted text-sm">
                  Loading comments…
                </div>
              )}

              {(
                comments.data?.items ??
                []
              ).map((comment) => (
                <div
                  key={comment.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="flex justify-between gap-3">
                    <div className="muted text-xs break-all">
                      {comment.author_user_id}
                    </div>

                    <span className="muted text-xs">
                      {comment.status}
                    </span>
                  </div>

                  <p className="text-sm mt-3 whitespace-pre-wrap">
                    {comment.body}
                  </p>

                  <div className="flex gap-2 mt-3">
                    {comment.status ===
                      "resolved" ? (
                      <button
                        className="btn btn-secondary text-xs"
                        disabled={
                          reopenComment.isPending
                        }
                        onClick={() =>
                          reopenComment.mutate(
                            comment.id,
                          )
                        }
                      >
                        Reopen
                      </button>
                    ) : (
                      <button
                        className="btn btn-secondary text-xs"
                        disabled={
                          resolveComment.isPending
                        }
                        onClick={() =>
                          resolveComment.mutate(
                            comment.id,
                          )
                        }
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {!comments.isPending &&
                !comments.data?.items
                  .length && (
                  <div className="muted text-sm">
                    No comments on this version.
                  </div>
                )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="font-semibold">
              Review tasks
            </h2>

            <input
              className="input mt-4"
              placeholder="Task title"
              value={taskTitle}
              onChange={(event) =>
                setTaskTitle(
                  event.target.value,
                )
              }
            />

            <textarea
              className="input mt-3 min-h-24 resize-y"
              placeholder="Description"
              value={taskDescription}
              onChange={(event) =>
                setTaskDescription(
                  event.target.value,
                )
              }
            />

            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              <select
                className="input"
                value={taskSeverity}
                onChange={(event) =>
                  setTaskSeverity(
                    event.target.value,
                  )
                }
              >
                <option value="info">
                  info
                </option>
                <option value="warning">
                  warning
                </option>
                <option value="error">
                  error
                </option>
                <option value="critical">
                  critical
                </option>
              </select>

              <input
                className="input"
                placeholder="Assignee UUID (optional)"
                value={taskAssignee}
                onChange={(event) =>
                  setTaskAssignee(
                    event.target.value,
                  )
                }
              />
            </div>

            <button
              className="btn btn-primary mt-3"
              disabled={
                !taskTitle.trim() ||
                createTask.isPending
              }
              onClick={() =>
                createTask.mutate()
              }
            >
              {createTask.isPending
                ? "Creating…"
                : "Create task"}
            </button>

            {createTask.error && (
              <ErrorMessage
                message={
                  createTask.error.message
                }
              />
            )}

            <div className="mt-5 space-y-3">
              {reviewTasks.isPending && (
                <div className="muted text-sm">
                  Loading review tasks…
                </div>
              )}

              {(
                reviewTasks.data?.items ??
                []
              ).map((task) => (
                <div
                  key={task.id}
                  className="rounded-xl border p-4"
                  style={{
                    borderColor:
                      "var(--line)",
                  }}
                >
                  <div className="flex justify-between gap-3">
                    <div>
                      <div className="font-medium">
                        {task.title}
                      </div>

                      <div className="muted text-xs mt-1">
                        {task.severity}
                      </div>
                    </div>

                    <select
                      className="input !w-auto text-xs"
                      value={task.status}
                      onChange={(event) =>
                        changeTaskStatus.mutate(
                          {
                            taskId:
                              task.id,
                            status:
                              event.target
                                .value,
                          },
                        )
                      }
                    >
                      <option value="open">
                        open
                      </option>
                      <option value="in_progress">
                        in_progress
                      </option>
                      <option value="resolved">
                        resolved
                      </option>
                      <option value="dismissed">
                        dismissed
                      </option>
                    </select>
                  </div>

                  {task.description && (
                    <p className="muted text-sm mt-3 whitespace-pre-wrap">
                      {task.description}
                    </p>
                  )}

                  {task.assignee_user_id && (
                    <div className="muted text-xs mt-3 break-all">
                      Assignee:{" "}
                      {task.assignee_user_id}
                    </div>
                  )}

                  {task.resolution && (
                    <pre className="muted text-xs mt-3 overflow-auto rounded-lg border p-3">
                      {JSON.stringify(
                        task.resolution,
                        null,
                        2,
                      )}
                    </pre>
                  )}
                </div>
              ))}

              {!reviewTasks.isPending &&
                !reviewTasks.data
                  ?.items.length && (
                  <div className="muted text-sm">
                    No review tasks for this
                    version.
                  </div>
                )}
            </div>
          </section>
        </div>
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

function ErrorMessage({
  message,
}: {
  message: string;
}) {
  return (
    <div
      className="text-sm mt-3"
      style={{
        color: "var(--danger)",
      }}
    >
      {message}
    </div>
  );
}