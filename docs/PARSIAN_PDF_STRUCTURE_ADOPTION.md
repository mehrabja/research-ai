# Parsian PDF structure extraction — adoption assessment

**Decision status:** benchmark first; do not enable production execution yet  
**Research AI base:** `9fc67dc9700fc9285ef56627532c7e5e08a5f1bf`  
**Parsian Science source reviewed:** `f23fa720c3600d48305fe39459df624b63e5393c`  
**Upstream package:** `packages/pdf-structure`

## 1. Capability gap

Research AI currently extracts PDF text page by page with `pypdf`, then canonicalizes the page text, preserves page boundaries and produces provenance-aware text chunks. This is appropriate for text retrieval, but it does not provide a first-class representation of scientific tables, figure crops, cell geometry, or caption-to-figure/table relationships.

Parsian's `@aipoch/pdf-structure` is a separate figure/table extraction engine. It is not a replacement for the existing text extraction pipeline: its output is a structured visual derivative that should complement the original PDF and canonical text.

## 2. What the upstream package actually requires

The reviewed package is Apache-2.0 licensed and is private to the Parsian monorepo. Its README describes an offline Node engine that accepts a disposable PDF snapshot and caller-supplied local model assets.

| Requirement | Upstream contract |
|---|---|
| Runtime | Node.js 22.13.0 or newer |
| Package dependencies | `pdfjs-dist`, `@napi-rs/canvas`, `sharp`, `tesseract.js`, `zod` |
| PDF input | Maximum 50 MiB |
| Requested pages | 1–5 pages per extraction |
| Worker output | Bounded to 4 MiB by the engine adapter |
| Models | Microsoft Table Transformer detection + structure recognition ONNX weights |
| Model assets | Caller-supplied local paths; package does not download or choose model revisions |
| Job ownership | Host supplies source authorization, immutable staging, model leases, scheduling, cache publication and cleanup |
| Process supervision | Host must confirm process termination before releasing job files or model leases |

The reviewed Parsian model catalog pins two ONNX weights of 115,694,355 and 115,811,109 bytes, plus the ONNX Runtime Web WASM runtime and notices. The complete table-model asset set is approximately 245.5 MB before optional OCR-language assets. The package's source/resource tree contains 183 runtime resources; its complete package directory is approximately 70 MB including tests and fixtures.

The package explicitly warns that a Worker/child-process boundary alone is not an OS sandbox. Parsian's host adds process-tree supervision, source authority, disposable snapshots, model-use leases, a bounded queue and a separately owned cache. These host responsibilities are as important as the parser itself.

## 3. Integration decision

**Do not import this package into the FastAPI process and do not replace `PdfExtractor`.**

The compatible target is an optional Node 22.13+ worker container behind the existing durable Python job system. The API and existing worker remain the system of record for tenants, authorization, source versions, job status and artifact publication.

Proposed data flow:

1. The authenticated API resolves the report-scoped source and immutable source version. The client never supplies a filesystem path, checksum, model path or arbitrary worker URL as an authority grant.
2. The Python job worker verifies the source identity and stages a private, immutable snapshot. It submits the bytes or a tightly scoped internal artifact reference to the PDF worker over an authenticated internal channel.
3. The Node worker accepts only bounded PDF input, a bounded page selection and an application-selected model revision. It creates a unique per-job directory and runs the upstream engine inside a non-root container with read-only model assets, no general network egress, CPU/memory/PID limits and a hard wall-clock deadline.
4. The worker validates the result identity, page numbers, geometry, decoding budget and output size. A worker exit or timeout is not considered successful cleanup until the process/container is confirmed stopped.
5. The API reauthorizes the source after processing and persists the structured result and thumbnails as separate, versioned derivatives. It does not overwrite `full_text`, canonical pages or existing text chunks.
6. The UI exposes tables/figures as source-linked evidence, with page/region provenance and an explicit extraction status. A model-produced table is never treated as a verified scientific claim.

The worker cache must be tenant/workspace scoped. The upstream cache identity includes engine fingerprint, source checksum and requested pages, but does not itself include a Research AI workspace boundary. A host adapter must not allow a cache hit to bypass source authorization or tenant isolation.

## 4. Benchmark gate before production adoption

The first deliverable is an offline evaluation, not a production feature flag. Use only synthetic documents and papers whose test use is permitted. Do not commit user uploads, private papers or model weights as fixtures.

The evaluation set should include at least:

- born-digital papers with ordinary ruled and unruled tables;
- multi-page tables, merged cells, wrapped headers and footnotes;
- figures with multi-panel layouts, sub-captions, legends and nearby prose;
- rotated pages and mixed page sizes;
- scanned pages and low-resolution figures;
- malformed, encrypted and oversized PDFs.

Compare the candidate with the current Research AI ingestion output and record per-document results. Required measurements:

- table and figure region precision/recall and region intersection-over-union;
- cell text accuracy, row/column structure, merged-cell reconstruction and reading order;
- caption association precision/recall;
- page number and region-coordinate provenance correctness;
- extraction failure classification, latency, peak RSS and output bytes;
- cancellation/timeout behavior and confirmed worker termination.

A successful JSON schema parse is not evidence that a table or figure is semantically correct. The benchmark report must preserve per-layout failures; a single aggregate score must not hide catastrophic errors in scientific tables, units or labels.

**Production gate:** adopt only if the candidate gives measurable benefit over the current pipeline on the curated benchmark, preserves source/page/region provenance, meets deployment resource limits, and demonstrates reliable termination and tenant isolation. Otherwise retain text-only extraction.

## 5. License and asset handling

The upstream package declares Apache-2.0. The Table Transformer model weights are separately identified as MIT in the Parsian model catalog; ONNX Runtime assets carry their own license and third-party notices. These are separate license obligations.

If source is imported later:

- retain the package's Apache-2.0 LICENSE and record the exact upstream commit and imported paths;
- preserve the Table Transformer, ONNX Runtime and OCR notices that correspond to the actually shipped assets;
- pin model revision, asset size and SHA-256 in an application-owned catalogue;
- keep weights out of Git and do not download or execute mutable model assets during a PDF job;
- do not treat an open-access paper or a valid parser result as permission to redistribute its PDF or extracted images.

## 6. Implementation sequence

1. Build the offline benchmark fixture set and evaluation report format.
2. Add a minimal Node worker container and verify health, bounded input, result decoding, cancellation and process-tree teardown without enabling end-user jobs.
3. Add the Python worker client, durable job state and tenant-scoped derivative persistence.
4. Run the benchmark and resource tests in CI using generated fixtures; keep model-backed inference as an opt-in acceptance lane that requires the pinned model assets.
5. Enable a feature flag for selected workspaces only after the production gate passes.

Until those steps pass, the existing pypdf extraction remains authoritative and this capability remains unavailable in the product UI.
