"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCodeAnalysis,
  getDataProfile,
  listCodeDependencies,
  listCodeSymbols,
  listDataColumns,
  type CodeAnalysis,
  type CodeDependency,
  type CodeSymbol,
  type DataColumnProfile,
  type DataProfile,
} from "@/lib/api/file-intelligence";
import { queryKeys } from "@/lib/query-keys";

type Props = {
  fileId: string;
  filename: string;
  fileKind: string;
};

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

function QueryError({ error }: { error: unknown }) {
  return (
    <div className="card pad" role="alert">
      <strong>Intelligence unavailable</strong>
      <p className="muted small" style={{ marginTop: 6 }}>
        {error instanceof Error ? error.message : "Unable to load analysis."}
      </p>
    </div>
  );
}

function CodePanel({ fileId }: { fileId: string }) {
  const analysis = useQuery({
    queryKey: queryKeys.fileCodeAnalysis(fileId),
    queryFn: () => getCodeAnalysis(fileId),
    staleTime: 15_000,
  });
  const symbols = useQuery({
    queryKey: queryKeys.fileCodeSymbols(fileId),
    queryFn: () => listCodeSymbols(fileId, 100, 0),
    staleTime: 15_000,
  });
  const dependencies = useQuery({
    queryKey: queryKeys.fileCodeDependencies(fileId),
    queryFn: () => listCodeDependencies(fileId, 100, 0),
    staleTime: 15_000,
  });

  if (analysis.isPending || symbols.isPending || dependencies.isPending) {
    return (
      <section className="card pad" aria-busy="true">
        <div className="eyebrow">Code intelligence</div>
        <h3>Analyzing code…</h3>
        <p className="muted small">Loading parser output, symbols and dependencies.</p>
      </section>
    );
  }

  if (analysis.error) return <QueryError error={analysis.error} />;
  if (symbols.error) return <QueryError error={symbols.error} />;
  if (dependencies.error) return <QueryError error={dependencies.error} />;

  const a = analysis.data as CodeAnalysis;
  const symbolItems = symbols.data?.items ?? [];
  const dependencyItems = dependencies.data?.items ?? [];

  return (
    <section className="stack" style={{ gap: 12 }}>
      <div className="grid grid-4">
        <div className="card metric"><div className="label">Language</div><div className="value" style={{ fontSize: 22 }}>{a.language}</div><div className="delta">{a.parser}</div></div>
        <div className="card metric"><div className="label">Lines</div><div className="value">{fmtNumber(a.line_count)}</div><div className="delta">{fmtNumber(a.character_count)} chars</div></div>
        <div className="card metric"><div className="label">Symbols</div><div className="value">{fmtNumber(a.symbol_count)}</div><div className="delta">{fmtNumber(a.function_count)} functions · {fmtNumber(a.class_count)} classes</div></div>
        <div className="card metric"><div className="label">Complexity</div><div className="value">{a.complexity_score === null ? "—" : a.complexity_score.toFixed(2)}</div><div className="delta">{fmtNumber(a.import_count)} imports · {a.parse_status}</div></div>
      </div>
      <div className="grid grid-2">
        <section className="card pad">
          <div className="row"><div><h3>Symbols</h3><div className="muted small">{symbols.data?.total ?? 0} extracted symbols</div></div></div>
          <div className="list" style={{ marginTop: 10 }}>
            {symbolItems.slice(0, 20).map((symbol: CodeSymbol) => (
              <article className="list-item" key={symbol.id}>
                <div className="row"><div style={{ minWidth: 0 }}><div className="title">{symbol.name}</div><div className="meta">{symbol.symbol_type} · lines {symbol.line_start}–{symbol.line_end}</div></div><span className="tag">{symbol.qualified_name}</span></div>
                {symbol.signature && <div className="muted small" style={{ marginTop: 6 }}>{symbol.signature}</div>}
              </article>
            ))}
            {symbolItems.length === 0 && <div className="empty">No symbols were extracted.</div>}
          </div>
        </section>
        <section className="card pad">
          <div className="row"><div><h3>Dependencies</h3><div className="muted small">{dependencies.data?.total ?? 0} dependencies</div></div></div>
          <div className="list" style={{ marginTop: 10 }}>
            {dependencyItems.slice(0, 30).map((dependency: CodeDependency) => (
              <article className="list-item" key={dependency.id}>
                <div className="row"><div className="title">{dependency.dependency_name}</div><span className="tag">{dependency.dependency_type}</span></div>
                <div className="meta" style={{ marginTop: 5 }}>{dependency.line_number ? "line " + dependency.line_number : "line n/a"}{dependency.is_relative ? " · relative import" : ""}</div>
              </article>
            ))}
            {dependencyItems.length === 0 && <div className="empty">No dependencies were extracted.</div>}
          </div>
        </section>
      </div>
    </section>
  );
}

function DataPanel({ fileId }: { fileId: string }) {
  const profile = useQuery({
    queryKey: queryKeys.fileDataProfile(fileId),
    queryFn: () => getDataProfile(fileId),
    staleTime: 15_000,
  });
  const columns = useQuery({
    queryKey: queryKeys.fileDataColumns(fileId),
    queryFn: () => listDataColumns(fileId, 200, 0),
    staleTime: 15_000,
  });

  if (profile.isPending || columns.isPending) {
    return <section className="card pad" aria-busy="true"><div className="eyebrow">Data intelligence</div><h3>Profiling data…</h3><p className="muted small">Loading schema, quality and column statistics.</p></section>;
  }
  if (profile.error) return <QueryError error={profile.error} />;
  if (columns.error) return <QueryError error={columns.error} />;

  const p = profile.data as DataProfile;
  const items = columns.data?.items ?? [];

  return (
    <section className="stack" style={{ gap: 12 }}>
      <div className="grid grid-4">
        <div className="card metric"><div className="label">Format</div><div className="value" style={{ fontSize: 22 }}>{p.format}</div><div className="delta">{p.profile_status}</div></div>
        <div className="card metric"><div className="label">Rows</div><div className="value">{fmtNumber(p.row_count)}</div><div className="delta">Observed rows</div></div>
        <div className="card metric"><div className="label">Columns</div><div className="value">{fmtNumber(p.column_count)}</div><div className="delta">{items.length} profiles loaded</div></div>
        <div className="card metric"><div className="label">Profile</div><div className="value" style={{ fontSize: 22 }}>{p.profile_version}</div><div className="delta">{p.profile_error ? p.profile_error : "No profile errors"}</div></div>
      </div>
      <section className="card table-wrap">
        <div className="row" style={{ padding: "0 16px 12px" }}><div><h3>Column profiles</h3><div className="muted small">{columns.data?.total ?? 0} columns</div></div></div>
        <table className="table"><thead><tr><th>Column</th><th>Type</th><th>Nulls</th><th>Distinct</th><th>Min</th><th>Max</th><th>Mean</th></tr></thead>
        <tbody>
          {items.map((column: DataColumnProfile) => (
            <tr key={column.id}><td><div className="strong">{column.name}</div><div className="meta">#{column.ordinal + 1}</div></td><td><span className="tag">{column.inferred_type}</span></td><td>{fmtNumber(column.null_count)} · {pct(column.null_ratio)}</td><td>{fmtNumber(column.distinct_count)}</td><td>{column.min_value ?? "—"}</td><td>{column.max_value ?? "—"}</td><td>{column.mean === null ? "—" : column.mean.toLocaleString()}</td></tr>
          ))}
        </tbody></table>
        {items.length === 0 && <div className="empty" style={{ margin: 16 }}>No column profiles were returned.</div>}
      </section>
    </section>
  );
}

export default function FileIntelligencePanel({ fileId, filename, fileKind }: Props) {
  const queryClient = useQueryClient();
  const metadata = useQuery({
    queryKey: queryKeys.fileMeta(fileId),
    queryFn: () => import("@/lib/api/file-intelligence").then((m) => m.getProjectFile(fileId)),
    staleTime: 15_000,
  });

  if (metadata.isPending) return <section className="card pad" aria-busy="true"><div className="eyebrow">File intelligence</div><h3>Loading {filename}…</h3></section>;
  if (metadata.error) return <QueryError error={metadata.error} />;

  const file = metadata.data;
  const supportsCode = fileKind === "code";
  const supportsData = fileKind === "structured_data" || fileKind === "spreadsheet";

  return (
    <section className="stack" style={{ gap: 12 }} role="region" aria-label={"Intelligence for " + filename}>
      <section className="card pad">
        <div className="row"><div><div className="eyebrow">Selected file</div><h3 style={{ marginTop: 4 }}>{filename}</h3><p className="muted small" style={{ marginTop: 4 }}>{file.detected_mime_type ?? file.client_mime_type ?? "MIME n/a"} · sha256 {file.sha256.slice(0, 16)}…</p></div><div className="actions"><span className="tag success">{file.status}</span><button className="btn ghost" type="button" onClick={() => { void queryClient.invalidateQueries({ queryKey: ["file-meta", fileId] }); void queryClient.invalidateQueries({ queryKey: ["file-code-analysis", fileId] }); void queryClient.invalidateQueries({ queryKey: ["file-code-symbols", fileId] }); void queryClient.invalidateQueries({ queryKey: ["file-code-dependencies", fileId] }); void queryClient.invalidateQueries({ queryKey: ["file-data-profile", fileId] }); void queryClient.invalidateQueries({ queryKey: ["file-data-columns", fileId] }); }}>Refresh</button></div></div>
        <div className="grid grid-4" style={{ marginTop: 14 }}>
          <div><div className="muted tiny">Kind</div><strong>{file.file_kind}</strong></div>
          <div><div className="muted tiny">Size</div><strong>{file.size_bytes.toLocaleString()} bytes</strong></div>
          <div><div className="muted tiny">Extraction</div><strong>{file.extraction_status}</strong></div>
          <div><div className="muted tiny">Updated</div><strong>{new Date(file.updated_at).toLocaleString()}</strong></div>
        </div>
        {file.extraction_error && <p className="muted small" role="alert" style={{ marginTop: 10 }}>Extraction error: {file.extraction_error}</p>}
      </section>
      {supportsCode && <CodePanel fileId={fileId} />}
      {supportsData && <DataPanel fileId={fileId} />}
      {!supportsCode && !supportsData && <section className="card pad"><div className="eyebrow">Document intelligence</div><h3>Extraction state</h3><p className="muted small" style={{ marginTop: 6 }}>This file kind currently exposes metadata, extraction status and evidence synchronization. Additional document-specific analysis can build on the extracted corpus.</p><div className="pillbar" style={{ marginTop: 10 }}><span className="tag">{file.extension ?? "extension n/a"}</span><span className="tag">{file.detected_mime_type ?? "MIME n/a"}</span><span className="tag">{file.extraction_status}</span></div></section>}
    </section>
  );
}
