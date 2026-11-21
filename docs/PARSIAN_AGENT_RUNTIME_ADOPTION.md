# Parsian Agent Runtime adoption

## Scope of this increment (M40)

Research AI already owns durable workflow orchestration, a PostgreSQL job queue, report-scoped retrieval, provider selection, AI metering, approval policy and worker leases. The first Agent Runtime increment adds a durable conversation layer on those existing services rather than introducing a second scheduler or persistence authority.

The implementation in this increment provides:
- report-owned agent sessions and ordered user/assistant messages;
- asynchronous turns dispatched through the existing durable jobs queue;
- bounded recent-history prompt construction;
- report-scoped lexical retrieval with source/chunk/page provenance;
- configured Research AI generation-provider routing and AI-operation/token metering;
- strict validation of model citation labels against evidence retrieved for the same report;
- session/message ownership checks and a per-session single-active-turn guard.

## Explicitly not included

This is not a vendored copy of @aipoch/agent-harness, and it is not full feature parity with Parsian's TypeScript runtime. It does not yet provide model streaming, arbitrary tool execution, MCP access, generated-code execution, child-agent delegation, wait/respond interaction checkpoints, context compaction, or cross-worker session continuation. The first increment intentionally exposes no model-callable tools.

The upstream Parsian package is Apache-2.0 licensed and requires Node.js 22.13 or newer. Research AI remains a Python service; no Apache-licensed upstream source is copied in this increment. Any future source reuse must preserve the upstream license and notices and be reviewed as a separate dependency/vendor change.

## Trust and execution boundaries

- A session is bound to one authenticated user and one report. A project/workspace binding is captured at creation and rechecked by the worker.
- Evidence retrieval is constrained to the report's own source records. Model-created citations not present in the retrieved evidence list are replaced with an unverified-reference marker.
- Retrieved excerpts and conversation history are untrusted data, never system instructions.
- The worker uses the configured Research AI provider and existing AI metering. It does not accept user-supplied provider URLs, API keys, model endpoints, file paths or tools.
- Turns are serialized per session. Duplicate job delivery is guarded by a unique assistant reply reference to its source user message.
- Provider calls are not exactly-once. A process failure after a successful model call but before message persistence may incur a second provider call when the durable job retries. This runtime executes no external tools or other non-idempotent side effects.

## API surface

The API is report-scoped:
- POST /api/v1/reports/{report_id}/agent-runtime/sessions
- GET /api/v1/reports/{report_id}/agent-runtime/sessions
- GET /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}
- GET /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/messages
- POST /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/messages

The message endpoint returns HTTP 202 and a durable job ID. Clients poll the session/messages endpoints for completion in this increment. A future streaming transport can be added without changing the message ownership or evidence provenance contracts.

## Future increments

1. Add explicit run/turn records and resumable event cursors for browser reconnection.
2. Implement approval-gated host tools over existing orchestration ToolSpec definitions; do not expose arbitrary filesystem, shell or network access.
3. Add delegation only after isolated child-session storage, concurrency budgets, explicit capability allowlists, child authorization, cancellation/drain semantics and uncertain-effect reconciliation are implemented.
4. Add context compaction with versioned summaries treated as untrusted history, retaining the original messages as audit evidence.
5. Evaluate whether a separate Node runtime is justified. If adopted, isolate it behind a narrow internal protocol and retain PostgreSQL as the sole durable authority.
