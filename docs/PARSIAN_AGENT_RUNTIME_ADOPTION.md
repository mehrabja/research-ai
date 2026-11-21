# Parsian Agent Runtime adoption

## Scope of this increment (M40 + M40.1)

Research AI already owns durable workflow orchestration, a PostgreSQL job queue, report-scoped retrieval, provider selection, AI metering, approval policy and worker leases. The first Agent Runtime increment adds a durable conversation layer on those existing services rather than introducing a second scheduler or persistence authority.

The implementation in this increment provides:
- report-owned agent sessions and ordered user/assistant messages;
- asynchronous turns dispatched through the existing durable jobs queue;
- bounded recent-history prompt construction;
- report-scoped lexical retrieval with source/chunk/page provenance;
- configured Research AI generation-provider routing and AI-operation/token metering;
- strict validation of model citation labels against evidence retrieved for the same report;
- session/message ownership checks and a per-session single-active-turn guard;
- explicit allowlist of idempotent tools from the existing orchestration registry;
- strict JSON argument validation and one tool proposal per user turn;
- durable pending/approved/rejected/completed tool-call records;
- authenticated approve/reject endpoints and one-attempt execution jobs;
- result persistence before optional model-generated explanation.

## Explicitly not included

This is not a vendored copy of @aipoch/agent-harness, and it is not full feature parity with Parsian's TypeScript runtime. It does not provide model streaming, arbitrary tool execution, MCP access, generated-code execution, child-agent delegation, wait/respond interaction checkpoints, context compaction, or a Node sidecar. Model-callable requests are limited to the explicit idempotent host-tool allowlist; each request remains inert until an authenticated user approves it.

The upstream Parsian package is Apache-2.0 licensed and requires Node.js 22.13 or newer. Research AI remains a Python service; no Apache-licensed upstream source is copied in this increment. Any future source reuse must preserve the upstream license and notices and be reviewed as a separate dependency/vendor change.

## Trust and execution boundaries

- A session is bound to one authenticated user and one report. A project/workspace binding is captured at creation and rechecked by the worker.
- Evidence retrieval is constrained to the report's own source records. Model-created citations not present in the retrieved evidence list are replaced with an unverified-reference marker.
- Retrieved excerpts and conversation history are untrusted data, never system instructions.
- The worker uses the configured Research AI provider and existing AI metering. It does not accept user-supplied provider URLs, API keys, model endpoints, file paths, shell commands, arbitrary URLs or raw network requests.
- Agent tool proposals are limited to a hard-coded allowlist of registered ToolSpec entries. The server revalidates tool version, permission, idempotency and JSON arguments both when proposed and immediately before execution.
- Every tool call is stored as `pending` and is not executable until its authenticated session owner explicitly approves it. Rejection is persisted; approval is bound to the same session, user and report. Each approved execution job is configured for one attempt.
- Non-idempotent orchestration tools are excluded. Worker execution uses the existing orchestration executor and cannot run arbitrary code, SQL, shell or MCP methods.
- Only the bounded, secret-filtered output preview is persisted in the tool-call record and exposed to its owner; tool-created artifacts continue to use their existing ownership controls. The preview is stored before an optional model explanation is generated.
- Turns are serialized per session. Duplicate message replies are guarded by a unique assistant reply reference to their source user message. Tool-call rows are unique per session/user message.

## API surface

The API is report-scoped:
- POST /api/v1/reports/{report_id}/agent-runtime/sessions
- GET /api/v1/reports/{report_id}/agent-runtime/sessions
- GET /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}
- GET /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/messages
- POST /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/messages
- GET /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/tool-calls
- POST /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/tool-calls/{tool_call_id}/approve
- POST /api/v1/reports/{report_id}/agent-runtime/sessions/{session_id}/tool-calls/{tool_call_id}/reject

The message endpoint returns HTTP 202 and a durable job ID. Clients poll the session/messages endpoints for completion in this increment. A future streaming transport can be added without changing the message ownership or evidence provenance contracts.

## Future increments

1. Add explicit run/turn records and resumable event cursors for browser reconnection.
2. Add resumable interaction checkpoints and event cursors after the approve/reject lifecycle is exercised in the UI.
3. Add delegation only after isolated child-session storage, concurrency budgets, explicit capability allowlists, child authorization, cancellation/drain semantics and uncertain-effect reconciliation are implemented.
4. Add context compaction with versioned summaries treated as untrusted history, retaining the original messages as audit evidence.
5. Evaluate MCP adapters only through named, permissioned host tools with separate credential and tenancy review.
6. Evaluate whether a separate Node runtime is justified. If adopted, isolate it behind a narrow internal protocol and retain PostgreSQL as the sole durable authority.
