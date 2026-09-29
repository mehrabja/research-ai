# Research-AI — F10 Publication & Export

## Scope

F10 connects the publication workspace to the existing M33 publication-target
and compliance pipeline and adds deterministic report export.

The browser flow is:

`report → publication target → compliance run → checklist/findings → export`

## Publication target

The UI reads active target profiles from:

`GET /api/v1/publication-targets`

A report target selection is persisted with:

`POST /api/v1/reports/{report_id}/publication-target/select`

The current selection is read from:

`GET /api/v1/reports/{report_id}/publication-target/current`

No hard-coded venue, journal, citation count, or submission metrics are
rendered by the publication workspace.

## Compliance

The UI invokes the existing M33 persisted compliance engine through:

`POST /api/v1/reports/{report_id}/publication-compliance/generate`

The page then reads the persisted run, checklist, findings, and validation
state through the corresponding publication-compliance endpoints.

## Export

F10 adds:

`GET /api/v1/reports/{report_id}/publication/export?format=<format>`

Supported formats:

- `markdown`
- `html`
- `json`
- `docx`

The export service selects the latest final-review report version when the
report has reached `review_2`, `validating`, or `completed`. When no
final-review version is available, it falls back to the latest completed
manuscript prose run.

DOCX generation uses only the Python standard library, so no additional
runtime dependency is required.

## Verification

Backend API coverage includes all four export formats and validates that the
DOCX response is a readable ZIP package containing `word/document.xml`.

Frontend coverage includes the real publication page, report/project scoping,
and an empty state without synthetic publication metrics.
