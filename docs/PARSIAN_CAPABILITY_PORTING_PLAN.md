# Parsian capability-porting roadmap

## Scope and current baseline

This roadmap tracks capabilities identified in the Parsian Science comparison that are not yet present, are only partial, or need a deliberate integration path in Research AI. The goal is capability adoption into Research AI's Python/FastAPI, PostgreSQL, worker, provider, and Workbench architecture—not a wholesale copy of the upstream application.

The current baseline already includes Research AI's research discovery, literature analysis and screening, report-scoped retrieval/evidence, knowledge graph, files, research plans, grounded manuscript generation, citations, academic QA, humanization/translation, publication compliance, orchestration, workspace collaboration, provider routing/metering, and the durable approval-gated Agent Runtime with SSE replay, checkpoints, and bounded context compaction.

The current Agent Runtime remains a single model-proposed tool per user turn. Its checkpoints are durable turn/context boundaries, not snapshots of a process, Python kernel, or complete machine.

## Phase sequence

| Phase | Scope | Main deliverables | Depends on |
|---|---|---|---|
| 0 — Existing foundation | Preserve the current Research AI platform and Agent Runtime | Durable sessions/messages, explicit tool approval, worker lease fencing, streaming event journal, SSE replay, checkpoints, bounded compaction, existing orchestration and evidence provenance | Existing platform |
| 1 — Scientific connector platform | Catalog, policy, credentials, MCP transport, scientific connector onboarding | 48-entry connector catalog; normalized tool/resource contracts; workspace-scoped connections and secret references; safe MCP client; connector health/quotas; approval and audit integration; first priority connectors then the remaining catalog | Phase 0 |
| 2 — Multi-step Agent Runtime | Move beyond one proposal per user turn | Durable run/step model; sequential tool loop; bounded parallel calls; explicit continuation after tool results; cancellation; steer/inbox queue; retry/effect reconciliation; child-agent delegation with budgets and isolated ownership | Phases 0–1 |
| 3 — Model and agent protocols | Broaden provider/runtime compatibility | Native OpenAI Responses and Anthropic Messages adapters; protocol-neutral tool-call/result events; ACP adapters for Claude Code, OpenCode, Codex, CodeBuddy, and Pi where supported; protocol conformance tests | Phases 0–2 |
| 4 — Skills and specialists | Add reusable domain workflows without silently expanding permissions | Versioned skill manifest/schema; skill execution through registered capabilities; specialist profiles and independent model/provider configuration; trusted import/export; signing, provenance, review, and permission grants; initial scientific skill pack | Phases 1–3 |
| 5 — Literature and scientific file workspace | Complete research reading and scientific document interaction | Persistent collections/library; duplicate resolution; full-text state; reading workspace and PDF annotations; robust PDF/table/figure extraction; PDF translation workflow; viewers for PDF, Office, images, code, tables, sequences, and molecular formats | Existing file/literature services |
| 6 — Notebook and compute | Controlled interactive scientific computation | Persistent Python and R kernels; notebook save/export; REPL and environment management; syntax and network sandboxing; durable background execution; resource and time budgets; later SSH/Slurm/HPC adapters with explicit credentials and policy | Phases 1–2 and security isolation |
| 7 — Provenance and research exchange | Make outputs portable and auditable | Immutable artifact versions; lineage graph; checksums; captured dependency/environment manifests; bounded artifact replay and comparison; read-only .science import, fork semantics, and RO-Crate export | Phases 5–6 |
| 8 — Product distribution | Extend beyond the browser | Desktop packaging and auto-update; standalone CLI; Node/Task SDK; local service lifecycle; paired-device and cross-surface session control | Stable APIs and permission model from phases 1–7 |
| 9 — Workflow and localization UX | Close remaining product-surface gaps | Conversation branches, side chats, bookmarks, queued messages, richer editable workflow canvas where justified, complete Persian-first i18n/RTL, and refined notifications/search integration | Phases 2–8 |

## Phase 1 implementation slices

### 1A — Inventory and capability boundary (started in this increment)

- Add a typed, server-owned catalog containing the 48 connector IDs identified in Parsian's connector-builtins inventory.
- Expose catalog metadata only for reports bound to a project.
- Mark every entry catalog_only, executable=false, and requires_approval=true.
- Do not accept client-supplied server URLs, endpoint overrides, credentials, or MCP tool names.
- Do not add catalog entries to the model-callable Agent Runtime allowlist.

### 1B — Secure MCP transport (initial foundation implemented)

- Uses the official MCP Python SDK v2 over Streamable HTTP; arbitrary stdio/subprocess servers are not launched by the API or worker.
- MCP server profiles are deployment-owned JSON configuration. API clients can select a profile key only; they cannot submit endpoint URLs, host allowlists, or credential references.
- Profiles require HTTPS, an exact hostname allowlist, no URL userinfo/query/fragment, and the standard HTTPS port. Discovery rejects DNS answers containing non-public IP addresses; production deployments must additionally enforce outbound egress allowlists at the network/container layer to close DNS-rebinding races.
- Workspace-scoped registrations store only the deployment profile key and bounded discovery metadata. Endpoint URLs, auth secret references and secret values are never persisted in the connection table or returned by the API.
- Credentials resolve through the existing environment-backed SecretResolver. This is a deployment-level secret reference, not per-workspace Vault/KMS or OAuth credential storage; managed secret backends and per-workspace OAuth grants remain follow-on work.
- Discovery is read-only: tools, resources, resource templates and prompts are normalized into a bounded snapshot. Remote tool entries are tagged `untrusted_remote`, `requires_approval=true` and `executable=false`; discovery never adds them to the Agent Runtime allowlist.
- Owner/admin-only enable, disable and discovery endpoints are workspace-scoped and emit audit events. Discovery has bounded timeouts, pagination, item counts, event sizes and stored snapshot size. Network I/O is performed outside the database transaction.
- Remaining 1B hardening before broad rollout: network-level egress enforcement and DNS pinning, managed Vault/KMS credential resolution, per-workspace OAuth, server health/quotas and concurrency controls.

### 1C — Connector onboarding

Prioritize a small, testable vertical slice (KEGG, ChEMBL, ClinicalTrials.gov, Monarch, and BioSamples are initial candidates), then onboard the remaining catalog in domain batches. For each connector require documented upstream API/protocol, license/terms review, authentication model, rate limits, error taxonomy, provenance fields, fixture-based tests, and an explicit status of available/partial/not configured.

## Cross-cutting acceptance gates

1. Tenant isolation: a user cannot enumerate, inspect, invoke, or reuse another workspace's connector or secret.
2. Least privilege: no arbitrary URL, shell, filesystem, SQL, or unrestricted network capability is introduced through an MCP adapter.
3. Approval: tool proposals stay inert until the authorized user approves; approval is bound to the exact connector, tool schema version, arguments, workspace, report, and session.
4. Reliability: bounded timeouts/retries, idempotency or explicit uncertain-effect handling, cancellation, and durable event/audit history.
5. Provenance: connector, upstream resource/record identifier, retrieval timestamp, license/attribution metadata when available, and source URL are retained.
6. Validation: unit, API authorization, migration, provider/adapter contract, and E2E tests run in CI; do not call a phase complete until its required CI gates pass.

## Explicit non-goals and parity cautions

- Do not describe arbitrary shell/code execution, unrestricted network access, or raw user-supplied MCP servers as safe defaults.
- Do not claim deterministic whole-session/process/kernel restoration or generic full-machine snapshots. The upstream project does not establish that level of recovery as a general capability.
- Managed cloud GPU is not a confirmed upstream capability in the audited matrix.
- The upstream feature matrix marks the full user-facing Model Arena, complete human review board, and editable validated workflow DAG as incomplete or partial; they are not counted as upstream-complete parity targets here.
- Optional projects listed upstream as evaluation candidates are not treated as integrated capabilities.
