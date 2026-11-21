# Parsian Science integration — Research AI

## Integration strategy

Research AI remains the system of record: FastAPI, PostgreSQL, workspace authorization, durable jobs, provider metering, evidence, citation validation and manuscript versions stay in their existing ownership boundaries.

Parsian Science is an Electron/Node desktop research workbench derived from AIPOCH Open-Science. Its desktop host, Prisma persistence, Electron IPC and local-kernel lifecycle are not drop-in dependencies for this Next.js/FastAPI SaaS application. Importing the entire desktop tree would create a second application and a second persistence/security authority rather than integrate capabilities.

This integration is intentionally incremental and backend-backed.

## First vertical slice: Scientific Workbench UX

- Added a three-region research workbench: workflow library/history, live execution surface, and context inspector.
- Uses the existing Research AI orchestration API for strategy discovery, run creation, polling, history, pause/resume/cancel, approval and validation.
- Uses existing report-scoped sources, project knowledge-graph summary and registered orchestration tools.
- Retains Research AI project/report context and routes into Discovery, Literature, Evidence and Manuscript.
- Adapts the research-workspace interaction model from Parsian Science while using Research AI's existing color tokens, typography, navigation, routing and API client. No Parsian renderer bundle, Electron shell or proprietary asset has been copied.

## Capability transfer plan

1. Agent execution — evaluate the portable @aipoch/agent-harness separately from the Electron host. If adopted, run it behind a narrow, authenticated Node worker boundary; do not import Electron IPC, Prisma or desktop settings into FastAPI.
2. Scientific execution — adapt notebook/job contracts to Research AI's durable job system. Kernel execution must run in an isolated worker/container with CPU, memory, wall-clock, filesystem and network limits. Never execute notebook code inside the web or API process.
3. Connectors — add required scientific APIs through the existing provider/connector registry, with per-provider timeouts, rate limits, attribution, content-rights checks and tenant-scoped provenance.
4. PDF structure — benchmark-first adoption is specified in [the PDF structure adoption assessment](PARSIAN_PDF_STRUCTURE_ADOPTION.md). The upstream engine requires a Node 22.13+ worker, pinned local ONNX assets and host-owned authorization, immutable staging, tenant-scoped cache, process-tree termination and resource controls. Do not run it in FastAPI or replace pypdf until the benchmark and sandbox gates pass.
5. Round-table review — implemented as a durable orchestration strategy with three separate role-specific requests (disciplinary, methodology, evidence/provenance), followed by a synthesis request. Every perspective receives the same report-scoped retrieved excerpts; AI calls are metered, token/provider-call budgets are enforced, unsupported evidence references are surfaced, and the persisted node is human-approval gated. These are distinct prompts and requests using the configured Research AI provider/model, not separate agent runtimes or guaranteed independent model families.
6. Localization and UX — borrow interaction patterns, not the Electron design system wholesale. Keep Research AI navigation, responsive breakpoints, keyboard behavior and accessible controls.

## Provenance and licensing

Parsian Science's README states that it is based on AIPOCH/Open-Science. Its root license is Apache-2.0. Any future source-code import must preserve Apache-2.0 notices and original AIPOCH attribution, retain each third-party asset's own license, and record the exact upstream commit and imported paths. This UI-only vertical slice adapts product interaction concepts and does not copy upstream source files.

Upstream references:
- https://github.com/Ho3seinTork/Parsian_Science
- https://github.com/AIPOCH/Open-Science
- https://github.com/Ho3seinTork/Parsian_Science/blob/main/docs/ARCHITECTURE.md
- https://github.com/Ho3seinTork/Parsian_Science/blob/main/docs/THIRD_PARTY_LICENSES.md

## Scientific source connector: PubMed

Research AI now supports a deployment-selectable PubMed provider alongside Semantic Scholar. Set `SOURCE_SEARCH_PROVIDER=pubmed` to route the existing report-scoped source-search endpoint through NCBI E-utilities. The adapter performs one ESearch request followed by one ESummary request and normalizes PMID, title, authors, publication year, DOI and PubMed URL into the existing `SourceCandidate` contract. Abstract/full-text acquisition remains in the existing extraction pipeline.

NCBI settings are optional: `PUBMED_API_KEY`, `PUBMED_EMAIL`, `PUBMED_TOOL`, `PUBMED_BASE_URL`, timeout/retry settings and a conservative per-process request interval. The adapter sends the NCBI `tool` parameter on each request and includes email/API key only when configured. HTTP/auth/rate-limit/transport/response failures use the existing typed provider exceptions. `open_access_only` adds PubMed's `free full text[sb]` search filter; it does not claim that full text has been downloaded.

This is a focused adapter, not a copy of the full Parsian PubMed connector: ID conversion, Europe PMC full-text fetch, JATS parsing and PubTator are not part of this increment. No Electron, npm or XML parser dependency is added to the API.

## Scientific source connector: Crossref

Research AI supports Crossref Works discovery through the existing report-scoped source-search
provider contract. Set `SOURCE_SEARCH_PROVIDER=crossref`. The adapter uses bibliographic search,
optional publication-year bounds and a field-select list, capped at 1,000 returned records in one
request. It maps DOI, title, authors, publication year, publisher landing URL and citation count into
the shared `SourceCandidate` type. An optional `CROSSREF_MAILTO` puts requests in Crossref's polite
pool; the public-pool default is paced at one list query per second. An optional Metadata Plus key is
sent in Crossref's `crossref-api-key` header, not in the URL. Timeouts, bounded retries, Retry-After,
response-size limits and process-local serialization are enforced.

Crossref states that most bibliographic metadata is reusable but some deposited abstracts may be
copyrighted. This adapter therefore returns abstract text only when the record explicitly reports
CC BY, CC BY-SA, CC0 or public-domain licensing. In `open_access_only` mode it further filters to
records with one of those explicitly reusable licences; a generic `has-license` flag is not treated
as a sufficient licence. Unknown, non-commercial, no-derivatives or publisher-specific terms yield
bibliographic metadata without abstract text. Full-text PDF retrieval remains in the existing
controlled ingestion pipeline.

Official references:
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/

## Scientific source connector: arXiv

Research AI supports the official arXiv Atom API through the same report-scoped source-search
provider contract. Set `SOURCE_SEARCH_PROVIDER=arxiv`; no API key is required. The adapter maps
arXiv IDs (including legacy archive IDs and versioned IDs), title, authors, publication year, DOI,
abstract and canonical abstract URL into the existing `SourceCandidate` model. The adapter currently
requests a conservative maximum of 100 records per API call; the application's search limit is
clamped to that provider window. It applies an optional publication-year query and uses relevance
sorting. arXiv's Atom API does not expose a distinct OpenAlex-style open-access filter, so the
`open_access_only` flag has no filtering effect for this provider.

The adapter uses a standard-library XML parser, rejects DTD/entity declarations and malformed Atom
feeds, and detects arXiv's HTTP-200 API error feed instead of misclassifying it as a paper. Requests
are bounded by timeout, response-size, retry and result limits. A process-local request pacer defaults
to a minimum three-second interval between calls, following arXiv's API guidance; multi-worker
deployments should still coordinate aggregate egress if multiple workers share one source IP.

The arXiv abstract returned by its metadata API is stored as provider-supplied bibliographic metadata.
This does not grant a blanket licence to download, redistribute or reuse the full-text PDF. PDF
retrieval and full-text extraction remain in Research AI's controlled ingestion pipeline and must
continue to preserve per-paper licence and provenance information.

Official reference:
- https://info.arxiv.org/help/api/user-manual.html

## Scientific source connector: OpenAlex

Research AI now supports an optional OpenAlex Works provider through the existing report-scoped
source-search endpoint. Set `SOURCE_SEARCH_PROVIDER=openalex`; `OPENALEX_API_KEY` is optional for
bounded basic searches. The adapter uses the Works search endpoint, requests only bibliographic and
abstract-index fields, and maps OpenAlex work IDs, DOI, title, year, authors, publication landing page
and citation count into the existing `SourceCandidate` contract. It applies publication-year and
open-access filters at the provider and uses ordinary page-based pagination capped at 1,000 results
(10 pages maximum at 100 per page); it does not cursor-page or attempt bulk dataset downloads.

The optional key is sent as an Authorization bearer header, not embedded in request URLs. Timeouts,
bounded retries, `Retry-After` handling, response-size limits and a conservative process-local request
pacer are enforced. In multi-worker deployments, per-process pacing is not a shared API quota; use a
provider egress/rate-limit gateway if aggregate traffic can exceed the OpenAlex key/IP allowance.
A free key increases the daily budget and is required for cursor paging beyond the first page; this
adapter deliberately stays within the basic page-based result window.

Abstract inverted-index reconstruction is stricter than the OpenAlex `is_oa` flag: the adapter
returns reconstructed abstract text only where the best/primary location reports an explicitly
reusable license (CC BY, CC BY-SA, CC0, public domain). Unknown, NC, ND or undeclared licenses yield
metadata without an abstract. Open access does not imply blanket permission to reproduce abstract
text. PDF retrieval and full-text extraction remain in Research AI's existing controlled ingestion
pipeline.

Official references:
- https://help.openalex.org/api/authentication/
- https://help.openalex.org/api/paging/
- https://help.openalex.org/api/errors/

## Scientific source connector: Europe PMC

Research AI supports Europe PMC through the existing report-scoped source-search provider contract. Set `SOURCE_SEARCH_PROVIDER=europepmc`; no API key is required. The adapter uses the Europe PMC REST search endpoint with `resultType=core`, one bounded page (maximum 100 records), optional `PUB_YEAR` filtering and the provider's `OPEN_ACCESS:Y` filter. It maps Europe PMC source/id identity, title, author list, publication year, DOI, citation count and the canonical Europe PMC article URL into `SourceCandidate`.

Abstract text is returned only when the record carries an explicit reusable licence (CC BY, CC BY-SA, CC0 or public-domain marker). An Open Access flag alone is not treated as a text-reuse licence. Unknown, NC, ND or missing licences retain bibliographic metadata but omit the abstract. The adapter does not retrieve PDFs or claim that full text has been read; acquisition and extraction remain in the existing controlled ingestion pipeline.

The adapter follows Europe PMC cursor pages internally when needed, up to 10 pages and 1,000 accepted records per search. Each page retains the same query and filters, uses the returned cursor, and passes through response-size, timeout, retry and per-process pacing controls. Pagination stops on an empty page, missing/repeated cursor, requested result limit or the hard page cap; it does not claim that a capped result set is exhaustive.

Official references:
- https://europepmc.org/RestfulWebService
- https://dev.europepmc.org/docs

## Round-table review capability

The `roundtable_review` strategy is exposed by the existing orchestration API and Workbench strategy selector. It retrieves lexical report-scoped chunks, binds source references to existing source/chunk IDs, runs three role-specific reviewer calls, then synthesizes consensus, disagreements, priority actions and evidence gaps. Provider calls are recorded in the existing AI operation/usage ledger. The model-assisted node follows the configured human-approval policy.

Structured output is not treated as proof of truth. References invented by a model are filtered into `unsupported_evidence_refs`; unstructured output is retained as an explicitly unstructured review. Provider/model diversity is not claimed: all roles use the configured generation chain.

## Validation status

The merged integration's latest default-branch validation in this review is GitHub Actions CI run 44873906428 (commit `9fc67dc9700fc9285ef56627532c7e5e08a5f1bf`), with all four jobs successful:

- Backend: Ruff, mypy, Alembic upgrade/downgrade/upgrade, application import, smoke tests and pytest.
- Frontend: dependency install, TypeScript typecheck, unit tests, API-boundary audit and production build.
- E2E: database migration, Playwright browser setup and end-to-end tests.
- Docker: API image build.

The matching Secret Scan run 44873906422 also passed. Earlier historical `generic-api-key` findings were addressed with exact commit-scoped Gitleaks fingerprints in the repository root `.gitleaksignore`; no rule-wide or path-wide suppression is used.
