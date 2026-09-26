"""Application smoke test (M36).

Usage:
    python scripts/smoke_test.py

Verifies:
    * app imports cleanly
    * /api/v1/health/live returns 200 (proves route registered)
    * /api/v1/health/ready responds without crashing
    * startup/shutdown lifespan runs without error

Exit codes:
    0 - all good
    1 - one or more checks failed
"""
from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1]
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def main() -> int:
    try:
        from app.main import app
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: app import raised {type(exc).__name__}: {exc}")
        return 1

    print("OK: app imported")

    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: TestClient unavailable: {exc}")
        return 1

    with TestClient(app) as client:
        r = client.get("/api/v1/health/live")
        if r.status_code != 200:
            print(
                f"FAIL: /health/live returned {r.status_code}"
            )
            return 1
        print("OK: /api/v1/health/live -> 200")

        r = client.get("/api/v1/health/ready")
        if r.status_code not in (200, 503):
            print(
                f"FAIL: /health/ready returned unexpected "
                f"{r.status_code}"
            )
            return 1
        print(
            f"OK: /api/v1/health/ready -> {r.status_code}"
        )

    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())