"use client";

import { useWorkspace } from "@/components/app-shell";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export default function UsagePage() {
  const { workspaceId } = useWorkspace();

  const usage = useQuery({
    queryKey: ["usage", workspaceId],
    queryFn: () => api.usage(workspaceId!),
    enabled: !!workspaceId,
  });

  if (!workspaceId) {
    return (
      <div className="card p-6 muted">
        Loading workspace…
      </div>
    );
  }

  const items = usage.data?.items ?? [];

  const limited = items.filter(
    (item) => item.limit !== null,
  );

  const totalCurrent = items.reduce(
    (sum, item) =>
      sum + item.current,
    0,
  );

  const totalLimit = limited.reduce(
    (sum, item) =>
      sum + (item.limit ?? 0),
    0,
  );

  return (
    <div className="space-y-7">
      <header>
        <div className="kicker">
          Workspace consumption
        </div>

        <h1 className="text-3xl font-semibold mt-2">
          Usage
        </h1>

        <p className="muted mt-2 max-w-3xl">
          Current-period usage and entitlement limits
          are read from the authoritative workspace usage
          contract.
        </p>
      </header>

      {usage.isPending && (
        <div className="card p-6 muted">
          Loading usage…
        </div>
      )}

      {usage.error && (
        <div className="card p-6">
          <div
            style={{
              color: "var(--danger)",
            }}
          >
            Usage unavailable:{" "}
            {usage.error.message}
          </div>
        </div>
      )}

      {usage.data && (
        <>
          <section className="card p-5">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="font-semibold">
                  Billing period
                </h2>

                <p className="muted text-sm mt-1">
                  Workspace{" "}
                  {usage.data.workspace_id}
                </p>
              </div>

              <div className="text-right">
                <div className="muted text-xs">
                  Period
                </div>

                <div className="text-sm mt-1">
                  {formatDate(
                    usage.data.period_start,
                  )}{" "}
                  →{" "}
                  {formatDate(
                    usage.data.period_end,
                  )}
                </div>
              </div>
            </div>
          </section>

          <div className="grid md:grid-cols-3 gap-4">
            <Metric
              label="Tracked metrics"
              value={items.length}
            />

            <Metric
              label="Limited metrics"
              value={limited.length}
            />

            <Metric
              label="Current total"
              value={totalCurrent}
            />
          </div>

          <section className="card overflow-hidden">
            <div
              className="px-5 py-4 border-b"
              style={{
                borderColor:
                  "var(--line)",
              }}
            >
              <div className="font-semibold">
                Usage metrics
              </div>

              <div className="muted text-xs mt-1">
                Backend-reported counters and their
                corresponding entitlement limits.
              </div>
            </div>

            <div className="divide-y">
              {!items.length && (
                <div className="p-8 muted text-sm">
                  No usage metrics are currently
                  reported for this workspace.
                </div>
              )}

              {items.map((item) => {
                const percentage =
                  item.limit !== null &&
                  item.limit > 0
                    ? Math.min(
                        100,
                        (item.current /
                          item.limit) *
                          100,
                      )
                    : null;

                return (
                  <div
                    key={item.metric}
                    className="p-5"
                  >
                    <div className="flex flex-wrap justify-between gap-4">
                      <div className="min-w-0">
                        <div className="font-medium break-all">
                          {item.metric}
                        </div>

                        <div className="muted text-xs mt-1">
                          Unit: {item.unit}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="font-semibold">
                          {formatNumber(
                            item.current,
                          )}
                          {item.limit !==
                            null &&
                            " / " +
                              formatNumber(
                                item.limit,
                              )}
                        </div>

                        <div className="muted text-xs mt-1">
                          {item.limit ===
                          null
                            ? "No configured limit"
                            : `${formatNumber(
                                item.limit,
                              )} limit`}
                        </div>
                      </div>
                    </div>

                    {percentage !==
                      null && (
                      <div className="mt-4">
                        <div className="h-2 rounded-full overflow-hidden bg-black/5">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${percentage}%`,
                            }}
                          />
                        </div>

                        <div className="flex justify-between gap-3 mt-2">
                          <span className="muted text-xs">
                            {percentage.toFixed(
                              1,
                            )}
                            % used
                          </span>

                          <span className="muted text-xs">
                            {formatNumber(
                              Math.max(
                                0,
                                (item.limit ??
                                  0) -
                                  item.current,
                              ),
                            )}{" "}
                            remaining
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="font-semibold">
              Entitlement summary
            </h2>

            <div className="grid md:grid-cols-2 gap-4 mt-4">
              <SummaryRow
                label="Total current counters"
                value={formatNumber(
                  totalCurrent,
                )}
              />

              <SummaryRow
                label="Combined configured limits"
                value={
                  limited.length
                    ? formatNumber(
                        totalLimit,
                      )
                    : "No limits reported"
                }
              />

              <SummaryRow
                label="Period start"
                value={formatDate(
                  usage.data.period_start,
                )}
              />

              <SummaryRow
                label="Period end"
                value={formatDate(
                  usage.data.period_end,
                )}
              />
            </div>
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

function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{
        borderColor:
          "var(--line)",
      }}
    >
      <div className="muted text-xs">
        {label}
      </div>

      <div className="font-medium mt-1 break-all">
        {value}
      </div>
    </div>
  );
}

function formatDate(
  value: string,
) {
  return new Date(
    value,
  ).toLocaleString();
}

function formatNumber(
  value: number,
) {
  return value.toLocaleString();
}