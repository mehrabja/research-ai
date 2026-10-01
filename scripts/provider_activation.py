#!/usr/bin/env python3
"""Phase 20 provider activation/readiness gate."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


_PLACEHOLDER_MARKERS = ("YOUR_", "CHANGE_ME", "change_me", "dev-insecure", "example")


def env(name: str) -> str:
    return os.getenv(name, "").strip()


def configured(name: str) -> bool:
    value = env(name)
    return bool(value) and not any(marker in value for marker in _PLACEHOLDER_MARKERS)


def require_all(label: str, names: tuple[str, ...]) -> Check:
    return Check(label, all(configured(name) for name in names), "configured" if all(configured(name) for name in names) else "missing required configuration")


def http_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers=headers or {"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload if isinstance(payload, dict) else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def config_checks(strict: bool) -> list[Check]:
    generation = env("GENERATION_PROVIDER") or "openai"
    embedding = env("EMBEDDING_PROVIDER") or "openai"
    translation = env("TRANSLATION_PROVIDER") or "openai"
    source = env("SOURCE_DISCOVERY_PROVIDER") or "semantic_scholar"
    storage = env("FILE_STORAGE_BACKEND") or "local"
    email = env("EMAIL_PROVIDER") or "none"
    billing = env("BILLING_PROVIDER") or "none"
    detection = env("DETECTION_PROVIDER") or "heuristic"

    checks = [
        Check(
            "Generation credentials",
            generation != "openrouter" and generation != "openai"
            or (
                configured("OPENROUTER_API_KEY")
                if generation == "openrouter"
                else configured("GENERATION_OPENAI_API_KEY")
            ),
            f"configured {generation}",
        ),
        Check(
            "Embedding credentials",
            embedding not in ("openrouter", "openai")
            or (
                configured("OPENROUTER_API_KEY")
                if embedding == "openrouter"
                else configured("EMBEDDING_OPENAI_API_KEY")
            ),
            f"configured {embedding}",
        ),
        Check(
            "Translation credentials",
            translation not in ("openrouter", "openai")
            or (
                configured("OPENROUTER_API_KEY")
                if translation == "openrouter"
                else configured("GENERATION_OPENAI_API_KEY")
            ),
            f"configured {translation}",
        ),
        require_all("Semantic Scholar", ("SEMANTIC_SCHOLAR_API_KEY",)) if source == "semantic_scholar" and strict else Check("Semantic Scholar", True, "not active"),
        Check("OpenAlex", True, "configured" if configured("OPENALEX_API_KEY") else "optional/unkeyed"),
        Check("Crossref", True, "configured" if configured("CROSSREF_MAILTO") else "public REST"),
        Check("NCBI", True, "configured" if configured("NCBI_API_KEY") else "optional/unkeyed"),
        Check("Unpaywall", not strict or configured("UNPAYWALL_EMAIL"), "configured" if configured("UNPAYWALL_EMAIL") else "runtime required in strict mode"),
        Check("S3 object storage", storage != "s3" or all(configured(name) for name in ("STORAGE_ENDPOINT", "STORAGE_ACCESS_KEY_ID", "STORAGE_SECRET_ACCESS_KEY", "STORAGE_BUCKET")), "active" if storage == "s3" else "local backend"),
        Check("Resend email", email != "resend" or (configured("RESEND_API_KEY") and configured("EMAIL_FROM")), "active" if email == "resend" else "not active"),
        Check("Stripe billing", billing != "stripe" or (configured("STRIPE_SECRET_KEY") and configured("STRIPE_WEBHOOK_SECRET") and configured("STRIPE_PRICE_IDS")), "active" if billing == "stripe" else "not active"),
        Check(
            "AI detection provider",
            (
                (
                    configured("AI_DETECTION_API_KEY")
                    and (
                        (
                            configured("DETECTION_API_BASE_URL")
                            if detection == "http"
                            else True
                        )
                    )
                )
                if detection in ("http", "originality", "sapling")
                else (detection == "heuristic" and not strict)
            ),
            (
                f"active {detection}"
                if detection in ("http", "originality", "sapling")
                else "non-production baseline" if detection == "heuristic" else "unsupported provider"
            ),
        ),
    ]
    return checks


def external_check(name: str) -> Check:
    try:
        if name == "Sapling":
            if (env("DETECTION_PROVIDER") or "heuristic") != "sapling":
                return Check(name, True, "skipped; provider not active")
            key = env("SAPLING_API_KEY")
            if not key:
                return Check(name, False, "missing required configuration")
            base = env("DETECTION_SAPLING_BASE_URL") or "https://api.sapling.ai/api/v1"
            request = urllib.request.Request(
                base.rstrip("/") + "/account/status",
                headers={
                    "Accept": "application/json",
                    "Authorization": "Bearer " + key,
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                return Check(name, False, f"HTTP {exc.code}")
            ok = (
                response.status == 200
                and isinstance(payload, dict)
                and payload.get("api_access") is True
            )
            detail = (
                "read-only account status"
                if ok
                else f"account access unavailable: {payload.get('blocked_reason')}"
                if isinstance(payload, dict)
                else "unexpected response"
            )
            return Check(name, ok, detail)

        if name == "Originality.ai":
            if (env("DETECTION_PROVIDER") or "heuristic") != "originality":
                return Check(name, True, "skipped; provider not active")
            key = env("AI_DETECTION_API_KEY")
            if not key:
                return Check(name, False, "missing required configuration")
            base = env("DETECTION_ORIGINALITY_BASE_URL") or "https://api.originality.ai/api/v3"
            status, payload = http_json(
                base.rstrip("/") + "/account/balance",
                {"Accept": "application/json", "X-OAI-API-KEY": key},
            )
            return Check(
                name,
                status == 200 and "credits" in payload and "subscriptionCredits" in payload,
                "read-only verification",
            )

        if name == "OpenRouter":
            if not configured("OPENROUTER_API_KEY"):
                return Check(name, True, "skipped; no configured key")
            base = env("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            status, payload = http_json(base.rstrip("/") + "/models", {"Accept": "application/json", "Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"})
            return Check(name, status == 200 and bool(payload.get("data")), "read-only verification")

        if name == "S3 object storage":
            if (env("FILE_STORAGE_BACKEND") or "local") != "s3":
                return Check(name, True, "skipped; provider not active")
            required_names = (
                "STORAGE_ENDPOINT",
                "STORAGE_ACCESS_KEY_ID",
                "STORAGE_SECRET_ACCESS_KEY",
                "STORAGE_BUCKET",
            )
            if not all(configured(item) for item in required_names):
                return Check(name, False, "missing required configuration")
            try:
                import boto3
                from botocore.config import Config

                client = boto3.client(
                    "s3",
                    endpoint_url=env("STORAGE_ENDPOINT").rstrip("/"),
                    aws_access_key_id=env("STORAGE_ACCESS_KEY_ID"),
                    aws_secret_access_key=env("STORAGE_SECRET_ACCESS_KEY"),
                    region_name=env("STORAGE_REGION") or "auto",
                    config=Config(
                        signature_version="s3v4",
                        s3={"addressing_style": "path"},
                    ),
                )
                client.head_bucket(Bucket=env("STORAGE_BUCKET"))
                return Check(name, True, "read-only verification")
            except Exception as exc:
                return Check(name, False, type(exc).__name__)

        if name == "Stripe":
            if (env("BILLING_PROVIDER") or "none") != "stripe":
                return Check(name, True, "skipped; provider not active")
            key = env("STRIPE_SECRET_KEY")
            if not key:
                return Check(name, False, "missing required configuration")
            base = env("STRIPE_API_BASE_URL") or "https://api.stripe.com/v1"
            request = urllib.request.Request(
                base.rstrip("/") + "/balance",
                headers={
                    "Accept": "application/json",
                    "Authorization": "Bearer " + key,
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                return Check(name, False, f"HTTP {exc.code}")
            return Check(
                name,
                response.status == 200 and isinstance(payload, dict) and payload.get("object") == "balance",
                "read-only verification",
            )

        if name == "Semantic Scholar":
            if not configured("SEMANTIC_SCHOLAR_API_KEY"):
                return Check(name, True, "skipped; no configured key")
            query = urllib.parse.urlencode({"query": "transformer", "limit": "1", "fields": "paperId,title"})
            status, payload = http_json("https://api.semanticscholar.org/graph/v1/paper/search?" + query, {"Accept": "application/json", "x-api-key": env("SEMANTIC_SCHOLAR_API_KEY")})
            return Check(name, status == 200 and "data" in payload, "read-only verification")

        if name == "OpenAlex":
            params = {"search": "transformer", "per-page": "1"}
            if configured("OPENALEX_API_KEY"):
                params["api_key"] = env("OPENALEX_API_KEY")
            status, payload = http_json("https://api.openalex.org/works?" + urllib.parse.urlencode(params))
            return Check(name, status == 200 and "results" in payload, "read-only verification")

        if name == "Crossref":
            params = {"query.bibliographic": "transformer", "rows": "1"}
            if configured("CROSSREF_MAILTO"):
                params["mailto"] = env("CROSSREF_MAILTO")
            status, payload = http_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params), {"Accept": "application/json", "User-Agent": "Research-AI provider activation"})
            return Check(name, status == 200 and "message" in payload, "read-only verification")

        if name == "NCBI":
            params = {"db": "pubmed", "term": "transformer", "retmode": "json", "retmax": "1"}
            if configured("NCBI_API_KEY"):
                params["api_key"] = env("NCBI_API_KEY")
            status, payload = http_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params))
            return Check(name, status == 200 and "esearchresult" in payload, "read-only verification")

    except Exception as exc:
        return Check(name, False, type(exc).__name__)

    return Check(name, True, "configuration-only")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--external", action="store_true")
    args = parser.parse_args()

    checks = config_checks(args.strict)
    if args.external:
        checks.extend(
            external_check(name)
            for name in ("Sapling", "Originality.ai", "OpenRouter", "Stripe", "Semantic Scholar", "OpenAlex", "Crossref", "NCBI")
        )

    failures = [check for check in checks if not check.ok]
    for check in checks:
        print(f"{'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")

    if failures:
        print(f"Provider activation: FAIL ({len(failures)} check(s))")
        return 1

    print("Provider activation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
