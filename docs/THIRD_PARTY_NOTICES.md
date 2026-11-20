# Third-party notices

This is an initial notice for known license-sensitive dependencies identified during the 2026-11-20 OSS preparation review. It is not a complete generated SBOM. The exact license and notice files for all resolved direct and transitive packages must be verified before release.

| Dependency | Use in Research AI | Declared license | Notes |
|---|---|---|---|
| pypdf 7.1.1 | PDF text extraction | BSD-3-Clause | Replaces PyMuPDF in the OSS preparation branch. Preserve the upstream copyright notice and disclaimer when redistributing the library. |
| psycopg / psycopg-binary | PostgreSQL driver | LGPL-3.0-only for psycopg-binary | Preserve LGPL notices and review replacement/relinking requirements for the exact packaging and distribution model. |

## Removed from the proposed dependency set

| Dependency | Previous use | License concern | Change |
|---|---|---|---|
| PyMuPDF 1.28.2 | PDF text extraction | AGPL-3.0 or commercial license | Removed from the proposed API dependencies; replaced with pypdf. |

## Upstream references

- pypdf: https://pypi.org/project/pypdf/
- pypdf license: https://github.com/py-pdf/pypdf/blob/main/LICENSE
- psycopg-binary: https://pypi.org/project/psycopg-binary/
- PyMuPDF licensing: https://pymupdf.io/licensing
- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0

Do not treat this file as a substitute for an SBOM or a version-specific legal review. Regenerate the inventory from the exact locked environment when the npm lockfile and Python dependency set are finalized.
