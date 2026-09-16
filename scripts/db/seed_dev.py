#!/usr/bin/env python3
"""Development seed for research-ai.

Idempotent, standalone, and independent of Alembic internals.

Run:
    python scripts/db/seed_dev.py

Environment:
    DATABASE_URL    Postgres URL (e.g. postgresql+psycopg://...)

This script does NOT seed:
  * users
  * credit_transactions
  * usage_logs
  * reports

Only configuration-level data:
  * ai_tell_patterns
  * convergence_strategies
  * detection_thresholds (sample)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------------
# Load .env from the repository root, then from the current directory.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(Path.cwd() / ".env", override=False)


AI_TELL_ROWS = [
    # (language, domain, category, pattern, replacement_pool, severity, version)
    ("en", None, "hedging", "it is important to note that",
     ["notably,", "crucially,", "importantly,"], 2, "1.0.0"),
    ("en", None, "transition", "in conclusion",
     ["to sum up", "overall", "taken together"], 1, "1.0.0"),
    ("en", None, "lexical", "delve into",
     ["examine", "explore", "investigate"], 2, "1.0.0"),
    ("en", None, "lexical", "tapestry",
     ["mosaic", "interplay", "fabric"], 3, "1.0.0"),
    ("en", None, "lexical", "navigate the landscape",
     ["orient within the field", "map the terrain"], 3, "1.0.0"),
    ("en", None, "structure", "firstly, secondly, thirdly",
     ["first,", "next,", "finally,"], 2, "1.0.0"),
    ("fa", None, "hedging", "لازم به ذکر است که",
     ["به‌ویژه،", "نکته مهم آنکه،"], 2, "1.0.0"),
    ("fa", None, "lexical", "در نهایت",
     ["سرانجام،", "در جمع‌بندی،"], 1, "1.0.0"),
    ("es", None, "hedging", "es importante señalar que",
     ["conviene destacar que", "cabe subrayar que"], 2, "1.0.0"),
]

CONVERGENCE_STRATEGY_ROWS = [
    {
        "name": "lexical_diversification",
        "order_index": 10,
        "model": None,
        "temperature": None,
        "scope": "segment",
        "prompt_template": (
            "Rewrite the following segment to reduce lexical AI-tells while "
            "preserving meaning, numbers, and citations.\n\n"
            "Segment:\n{{segment}}\n\n"
            "Detected AI-tells:\n{{flagged_patterns}}"
        ),
        "techniques": {"replace_patterns": True, "paraphrase": False},
        "active": True,
        "version": "1.0.0",
    },
    {
        "name": "syntactic_variation",
        "order_index": 20,
        "model": None,
        "temperature": None,
        "scope": "paragraph",
        "prompt_template": (
            "Vary sentence length and structure in the paragraph below. "
            "Do not change claims, numbers, or citations.\n\n{{paragraph}}"
        ),
        "techniques": {"split_long_sentences": True, "merge_short_sentences": True},
        "active": True,
        "version": "1.0.0",
    },
    {
        "name": "voice_realignment",
        "order_index": 30,
        "model": None,
        "temperature": None,
        "scope": "paragraph",
        "prompt_template": (
            "Realign the paragraph to the target voice profile.\n\n"
            "Voice profile:\n{{voice_profile}}\n\nParagraph:\n{{paragraph}}"
        ),
        "techniques": {"match_formality": True, "match_first_person": True},
        "active": True,
        "version": "1.0.0",
    },
]

DETECTION_THRESHOLD_ROWS = [
    # (detector, domain, language, threshold, calibration_set_size, percentiles)
    ("default-detector", "general", "en", 0.25, 0, None),
    ("default-detector", "general", "fa", 0.30, 0, None),
    ("default-detector", "general", "es", 0.25, 0, None),
]


def _json(value: object) -> str:
    """Serialize a Python object to a JSON string for PostgreSQL casting."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def seed_ai_tell_patterns(engine: Engine) -> int:
    inserted = 0
    with engine.begin() as conn:
        for language, domain, category, pattern, pool, severity, version in AI_TELL_ROWS:
            result = conn.execute(
                text(
                    """
                    INSERT INTO ai_tell_patterns
                        (language, domain, category, pattern, replacement_pool,
                         severity, active, version)
                    SELECT :language, :domain, :category, :pattern,
                           CAST(:pool AS jsonb), :severity, TRUE, :version
                    WHERE NOT EXISTS (
                        SELECT 1 FROM ai_tell_patterns
                        WHERE language = :language
                          AND category = :category
                          AND pattern  = :pattern
                          AND COALESCE(domain, '') = COALESCE(:domain, '')
                    )
                    """
                ),
                {
                    "language": language,
                    "domain": domain,
                    "category": category,
                    "pattern": pattern,
                    "pool": _json(pool),
                    "severity": severity,
                    "version": version,
                },
            )
            inserted += result.rowcount or 0
    return inserted


def seed_convergence_strategies(engine: Engine) -> int:
    inserted = 0
    with engine.begin() as conn:
        for row in CONVERGENCE_STRATEGY_ROWS:
            result = conn.execute(
                text(
                    """
                    INSERT INTO convergence_strategies
                        (name, order_index, model, temperature, scope,
                         prompt_template, techniques, active, version)
                    VALUES
                        (:name, :order_index, :model, :temperature, :scope,
                         :prompt_template, CAST(:techniques AS jsonb),
                         :active, :version)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                {
                    "name": row["name"],
                    "order_index": row["order_index"],
                    "model": row["model"],
                    "temperature": row["temperature"],
                    "scope": row["scope"],
                    "prompt_template": row["prompt_template"],
                    "techniques": _json(row["techniques"]),
                    "active": row["active"],
                    "version": row["version"],
                },
            )
            inserted += result.rowcount or 0
    return inserted


def seed_detection_thresholds(engine: Engine) -> int:
    inserted = 0
    with engine.begin() as conn:
        for detector, domain, language, threshold, cal_size, percentiles in DETECTION_THRESHOLD_ROWS:
            result = conn.execute(
                text(
                    """
                    INSERT INTO detection_thresholds
                        (detector, domain, language, threshold,
                         calibration_set_size, percentiles)
                    VALUES
                        (:detector, :domain, :language, :threshold,
                         :cal_size, CAST(:percentiles AS jsonb))
                    ON CONFLICT (detector, domain, language) DO NOTHING
                    """
                ),
                {
                    "detector": detector,
                    "domain": domain,
                    "language": language,
                    "threshold": threshold,
                    "cal_size": cal_size,
                    "percentiles": _json(percentiles) if percentiles is not None else None,
                },
            )
            inserted += result.rowcount or 0
    return inserted


def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Copy .env.example to .env first.", file=sys.stderr)
        return 2

    engine = create_engine(url, future=True)

    print("Seeding ai_tell_patterns ...")
    n1 = seed_ai_tell_patterns(engine)

    print("Seeding convergence_strategies ...")
    n2 = seed_convergence_strategies(engine)

    print("Seeding detection_thresholds ...")
    n3 = seed_detection_thresholds(engine)

    print(
        f"Done. Inserted: ai_tell_patterns={n1}, "
        f"convergence_strategies={n2}, detection_thresholds={n3}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())