# Licensing and third-party material audit

**Audit snapshot:** 2026-11-20  
**Repository reviewed:** mehrabja/research-ai  
**Base ref reviewed:** m39-production-capabilities  
**Preparation ref:** oss-readiness/2026-11

This document records a repository-level pre-release review. It is not a legal opinion and is not a complete software bill of materials (SBOM).

## Project license decision

The proposed project license is **Apache License 2.0**.

Rationale:

- It is a widely used OSI-approved permissive license.
- It includes an express contributor patent grant and a patent-litigation termination clause.
- It permits use, modification, and redistribution subject to retaining the license and required notices.

The root LICENSE file and the API package license file are added on the preparation branch. The API package metadata is changed from Proprietary to the SPDX expression Apache-2.0.

Before merging, confirm that all project-owned code and documentation may be released under Apache-2.0 and keep the root and apps/api license copies identical.

## Material license issue found and remediation proposed

### PyMuPDF

The base branch declared PyMuPDF 1.28.2 and imported it in the source and uploaded-file PDF extraction paths. PyMuPDF is offered under AGPL-3.0 or a separate commercial license. An Apache-2.0 project should not silently ship an AGPL-linked dependency as though the whole dependency set were permissive.

The preparation branch replaces PyMuPDF with **pypdf 7.1.1**, whose published PyPI license expression is BSD-3-Clause. Both PDF extraction paths are updated to use PdfReader. The old PyMuPDF dependency is removed from the API dependency declarations and requirements snapshot.

This is a code change and must pass PDF regression tests before the branch is merged. Compare extraction behavior on representative PDFs, including encrypted, malformed, scanned, and text-based files. pypdf extracts embedded text; it is not an OCR engine.

### Psycopg 3 and binary extra

The API declares `psycopg[binary]`. PyPI marks both the pure-Python `psycopg` 3.3.5 distribution and the `psycopg-binary` extra distribution as **LGPL-3.0-only**. This dependency remains in the preparation branch.

Before redistributing built containers or binary bundles, verify the applicable LGPL obligations for the exact resolved versions and packaging model. Preserve the dependency's license and notices, and ensure recipients retain the rights the LGPL requires, including the ability to replace or modify the library where applicable. Do not describe the complete dependency graph as consisting only of MIT/BSD/Apache packages.

## Dependency inventory status

Direct runtime dependencies are declared in apps/api/pyproject.toml and pinned in apps/api/requirements.txt. Frontend direct dependencies are declared in apps/web/package.json.

Findings:

- The Python requirements file is a pinned package snapshot, but it is not a complete license report.
- The frontend currently has no package-lock.json or other npm lockfile.
- A transitive dependency inventory has not yet been generated for either ecosystem.
- The preparation branch adds pypdf and removes PyMuPDF from the tracked manifests.
- The exact license metadata for every resolved transitive package still needs automated verification.

Before public release, install the exact dependency sets and generate reports, for example:

~~~bash
cd apps/api
pip install -e ".[dev]"
pip install pip-licenses
pip-licenses --format=markdown --with-urls --with-license-file
~~~

For the frontend, create and commit package-lock.json, then run npm audit and a license inventory against the locked dependency tree. Review any GPL, AGPL, LGPL, SSPL, source-available, commercial-only, or custom-licensed dependency before release.

## Data, images, fonts, and other assets

A recursive tree review of the base branch found no obvious standalone datasets, PDF samples, notebooks, image files, videos, fonts, archives, or database dumps based on tracked paths and file extensions. The source tree did contain code, migrations, tests, environment templates, and documentation.

The backend includes a Semantic Scholar integration and source/document ingestion paths. Those integrations do not mean that external papers or datasets are licensed for redistribution. Provider API terms, rate limits, attribution requirements, and the copyright/licensing terms of material fetched or uploaded at runtime must be reviewed separately. Do not bundle downloaded papers, datasets, or user-provided documents in the public repository unless their licenses or explicit permissions allow redistribution.

This is not a complete content provenance review. It does not establish the license of:
- Small snippets, copied code, comments, or text embedded in source files.
- Any sample data constructed in Python or TypeScript fixtures.
- Logos, screenshots, fonts, or other assets added after this audit.
- External datasets or documents users may upload at runtime.

For each future image, logo, font, dataset, or test fixture, record the source, license, and required attribution before adding it.

## Required before public release

- [ ] Confirm Apache-2.0 is the intended license for the entire project.
- [ ] Verify root LICENSE and apps/api/LICENSE are byte-identical.
- [ ] Run the PDF regression suite after the pypdf migration.
- [ ] Generate a full Python and npm transitive dependency license report.
- [ ] Review LGPL obligations for psycopg/psycopg-binary in the intended distribution model.
- [ ] Generate and commit an npm lockfile.
- [ ] Review all data and media assets added after this audit.
- [ ] Review Git history for secrets and third-party material; a current-tree scan alone is insufficient.
