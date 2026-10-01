#!/usr/bin/env python3
"""Production/staging smoke checks for the Research-AI API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_PLACEHOLDER_MARKERS = ("YOUR_", "CHANGE_ME", "change_me", "dev-insecure", "example")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    if any(marker in value for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError(f"{name} contains a placeholder value; provide a real credential.")
    return value


def request(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(
        url,
        headers=headers or {"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def json_request(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], dict[str, Any]]:
    status, response_headers, body = request(url, headers)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{url} returned invalid JSON (HTTP {status}).") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} returned a non-object JSON payload.")
    return status, response_headers, payload


def expect(status: int, expected: int, label: str) -> None:
    if status != expected:
        raise RuntimeError(f"{label} failed: HTTP {status}, expected {expected}.")


def header_value(headers: dict[str, str], name: str) -> str | None:
    expected = name.lower()
    for key, value in headers.items():
        if key.lower() == expected:
            return value
    return None


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = os.getenv("SMOKE_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("SMOKE_API_KEY", "").strip()
    if token and any(marker in token for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError("SMOKE_ACCESS_TOKEN contains a placeholder value; provide a real credential.")
    if api_key and any(marker in api_key for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError("SMOKE_API_KEY contains a placeholder value; provide a real credential.")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif api_key:
        headers["X-API-Key"] = api_key
    return headers


def core_smoke(base_url: str, headers: dict[str, str]) -> None:
    for path, label in (
        ("/api/v1/health/live", "liveness"),
        ("/api/v1/health/ready", "readiness"),
        ("/openapi.json", "OpenAPI"),
    ):
        status, response_headers, _ = json_request(base_url + path, headers)
        expect(status, 200, label)
        request_id = header_value(response_headers, "X-Request-ID")
        if not request_id:
            raise RuntimeError(
                f"{label} is missing X-Request-ID; the deployed API may be stale or misconfigured."
            )
        print(f"PASS {label} request_id={request_id}")

    if "Authorization" not in headers and "X-API-Key" not in headers:
        print("INFO authenticated smoke skipped; set SMOKE_ACCESS_TOKEN or SMOKE_API_KEY.")
        return

    status, _, _ = json_request(base_url + "/api/v1/auth/me", headers)
    expect(status, 200, "authenticated user")
    print("PASS authenticated user")

    status, _, matrix = json_request(base_url + "/api/v1/providers/matrix", headers)
    expect(status, 200, "provider matrix")
    check_expected_providers(matrix)
    print("PASS provider matrix")

    status, _, _ = json_request(base_url + "/api/v1/projects?limit=1", headers)
    expect(status, 200, "project listing")
    print("PASS project listing")


def check_expected_providers(matrix: dict[str, Any]) -> None:
    expected_raw = os.getenv("SMOKE_EXPECT_PROVIDER", "").strip()
    if not expected_raw:
        return

    rows = {
        str(row.get("capability")): row
        for row in matrix.get("capabilities", [])
        if isinstance(row, dict)
    }

    for item in expected_raw.split(";"):
        if not item.strip():
            continue
        capability, separator, provider = item.partition("=")
        if not separator or not capability or not provider:
            raise RuntimeError(
                "SMOKE_EXPECT_PROVIDER must look like generation=openrouter;source_discovery=openalex."
            )
        row = rows.get(capability)
        if row is None:
            raise RuntimeError(f"Capability {capability!r} is missing.")
        configured = str(row.get("configured_preferred", ""))
        available = {str(value) for value in row.get("available_providers", [])}
        if configured != provider and provider not in available:
            raise RuntimeError(
                f"Provider {provider!r} is not configured/registered for {capability!r}."
            )


def external_get(
    label: str,
    url: str,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> None:
    status, _, _ = json_request(url, headers)
    expect(status, expected, label)
    print(f"PASS external {label}")


def verify_originality() -> None:
    key = required("AI_DETECTION_API_KEY")
    base = os.getenv(
        "DETECTION_ORIGINALITY_BASE_URL",
        "https://api.originality.ai/api/v3",
    ).rstrip("/")
    status, _, payload = json_request(
        base + "/account/balance",
        {"Accept": "application/json", "X-OAI-API-KEY": key},
    )
    expect(status, 200, "Originality.ai account balance")
    if not all(key in payload for key in ("credits", "subscriptionCredits")):
        raise RuntimeError("Originality.ai account balance returned an unexpected payload.")
    print("PASS external Originality.ai")


def verify_openrouter() -> None:
    key = required("OPENROUTER_API_KEY")
    base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    status, _, payload = json_request(
        base + "/models",
        {"Accept": "application/json", "Authorization": f"Bearer {key}"},
    )
    expect(status, 200, "OpenRouter models")
    if not payload.get("data"):
        raise RuntimeError("OpenRouter returned no models.")
    print("PASS external OpenRouter")


def verify_semantic_scholar() -> None:
    query = urllib.parse.urlencode({"query": "transformer", "limit": "1", "fields": "paperId,title"})
    headers = {"Accept": "application/json"}
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if key:
        headers["x-api-key"] = key
    external_get(
        "Semantic Scholar",
        "https://api.semanticscholar.org/graph/v1/paper/search?" + query,
        headers,
    )


def verify_openalex() -> None:
    params = {"search": "transformer", "per-page": "1"}
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if key:
        params["api_key"] = key
    external_get(
        "OpenAlex",
        "https://api.openalex.org/works?" + urllib.parse.urlencode(params),
    )


def verify_crossref() -> None:
    params = {"query.bibliographic": "transformer", "rows": "1"}
    mailto = os.getenv("CROSSREF_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    external_get(
        "Crossref",
        "https://api.crossref.org/works?" + urllib.parse.urlencode(params),
        {"Accept": "application/json", "User-Agent": "Research-AI production smoke"},
    )


def verify_ncbi() -> None:
    params = {"db": "pubmed", "term": "transformer", "retmode": "json", "retmax": "1"}
    key = os.getenv("NCBI_API_KEY", "").strip()
    if key:
        params["api_key"] = key
    external_get(
        "NCBI",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        + urllib.parse.urlencode(params),
    )


def verify_unpaywall() -> None:
    email = required("UNPAYWALL_EMAIL")
    doi = os.getenv("UNPAYWALL_SMOKE_DOI", "10.1038/s41586-020-2649-2")
    url = "https://api.unpaywall.org/v2/" + urllib.parse.quote(doi, safe="") + "?" + urllib.parse.urlencode({"email": email})
    external_get("Unpaywall", url)


def main() -> int:
    try:
        base_url = required("SMOKE_BASE_URL").rstrip("/")
        core_smoke(base_url, auth_headers())

        checks = {
            "SMOKE_VERIFY_ORIGINALITY": verify_originality,
            "SMOKE_VERIFY_OPENROUTER": verify_openrouter,
            "SMOKE_VERIFY_SEMANTIC_SCHOLAR": verify_semantic_scholar,
            "SMOKE_VERIFY_OPENALEX": verify_openalex,
            "SMOKE_VERIFY_CROSSREF": verify_crossref,
            "SMOKE_VERIFY_NCBI": verify_ncbi,
            "SMOKE_VERIFY_UNPAYWALL": verify_unpaywall,
        }
        for flag, checker in checks.items():
            if os.getenv(flag, "").strip().lower() in {"1", "true", "yes"}:
                checker()

        print("Production smoke: PASS")
        return 0
    except Exception as exc:
        print(f"Production smoke: FAIL — {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
