# Unified Phase 12-14 — Persistence & Evidence

Date: 2026-09-29
Branch: phase123-integration

## Scope

This unified phase closes the legacy roadmap items:

- Phase 12 — PDF Workspace persistence
- Phase 13 — Research Canvas persistence
- Phase 14 — File Intelligence to Evidence unification

## PDF Workspace

PDF documents reuse the existing project-file storage boundary. A project receives a
persistent PDF workspace state containing the active PDF, page, zoom, and scroll position.

Highlights and notes are stored as tenant-scoped annotations tied to the source PDF file.
The workspace exposes only PDF project files owned by the authenticated user.

API:

- GET /api/v1/projects/{project_id}/pdf-workspace
- PUT /api/v1/projects/{project_id}/pdf-workspace
- POST /api/v1/projects/{project_id}/pdf-workspace/annotations
- PATCH /api/v1/projects/{project_id}/pdf-workspace/annotations/{annotation_id}
- DELETE /api/v1/projects/{project_id}/pdf-workspace/annotations/{annotation_id}

## Research Canvas

Each project has one persisted canvas document with revision-based optimistic concurrency.
Nodes, edges, and viewport state are validated server-side and stored together.

API:

- GET /api/v1/projects/{project_id}/research-canvas
- PUT /api/v1/projects/{project_id}/research-canvas

A stale expected_revision returns 409 CANVAS_REVISION_CONFLICT.

## File Intelligence to Evidence

The existing ProjectFile -> Source -> Chunk bridge remains the canonical evidence path.
The new project evidence contract exposes extraction state, source/chunk coverage, and report
linkage without introducing a second evidence store.

API:

- GET /api/v1/projects/{project_id}/evidence/files
- POST /api/v1/projects/{project_id}/evidence/sync

Ready extracted files are automatically synchronized into report-local Source/Chunk rows
during extraction and report creation. Deleted/failed files retain provenance rows but are
removed from active retrieval.

## Acceptance

Backend API tests cover persistence, cross-user isolation, revision conflicts, and file-to-source
mapping. Frontend E2E covers PDF state persistence, canvas persistence, and the project-level
file evidence surface.
