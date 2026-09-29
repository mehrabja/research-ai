"use client";

import { useQuery } from "@tanstack/react-query";
import type { components } from "@/lib/api/schema";
import { api } from "@/lib/api/client";
import { apiErrorFromUnknown } from "@/lib/api/errors";

type ProviderCapability =
  components["schemas"]["ProviderCapabilityRead"];

async function getProviderMatrix(): Promise<ProviderCapability[]> {
  const result = await api.GET(
    "/api/v1/providers/matrix",
  );
  const response = (result as { response: Response }).response;

  if (result.error || !result.data) {
    throw apiErrorFromUnknown(result.error, {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      fallback: "Provider matrix request failed",
    });
  }

  return result.data.capabilities;
}

const LABELS: Record<string, string> = {
  generation: "Generation",
  embedding: "Embeddings",
  translation: "Translation",
  detection: "AI detection",
  source_discovery: "Source discovery",
  billing: "Billing",
  email: "Transactional email",
  storage: "Object storage",
};

export function ProviderMatrixView() {
  const query = useQuery({
    queryKey: ["provider-matrix"],
    queryFn: getProviderMatrix,
    staleTime: 30_000,
  });

  if (query.isPending) {
    return (
      <section className="card pad" aria-busy="true">
        <h3>Provider matrix</h3>
        <p className="muted small">
          Loading registered provider capabilities…
        </p>
      </section>
    );
  }

  if (query.error) {
    const message =
      query.error instanceof Error
        ? query.error.message
        : "Provider matrix request failed";
    return (
      <section className="card pad" role="alert">
        <div className="row">
          <div>
            <h3>Provider matrix unavailable</h3>
            <p className="muted small">{message}</p>
          </div>
          <button
            className="btn ghost"
            type="button"
            onClick={() => void query.refetch()}
          >
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="card pad" aria-label="Provider matrix">
      <div className="row">
        <div>
          <h3>Provider matrix</h3>
          <p className="muted small">
            Active registry capabilities visible to this authenticated
            session.
          </p>
        </div>
        <span className="tag success">
          {query.data.length} capabilities
        </span>
      </div>

      <div className="table-wrap" style={{ marginTop: 14 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Capability</th>
              <th>Preferred</th>
              <th>Registered providers</th>
            </tr>
          </thead>
          <tbody>
            {query.data.map((item) => (
              <tr key={item.capability}>
                <td>
                  <strong>
                    {LABELS[item.capability] ?? item.capability}
                  </strong>
                </td>
                <td>
                  {item.configured_preferred ? (
                    <span className="tag">{item.configured_preferred}</span>
                  ) : (
                    <span className="muted small">Not configured</span>
                  )}
                </td>
                <td>
                  <div className="pillbar">
                    {item.available_providers.map((provider) => (
                      <span className="tag" key={provider}>
                        {provider}
                      </span>
                    ))}
                    {item.available_providers.length === 0 && (
                      <span className="muted small">
                        No adapter registered
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
