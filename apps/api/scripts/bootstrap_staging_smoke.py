#!/usr/bin/env python3
"""Create an ephemeral, pre-verified staging smoke account inside the runtime."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.db.session import SessionLocal
from app.services import auth as auth_service

CREDENTIAL_PATH = Path("/run/research-ai/smoke-credentials.json")


def main() -> int:
    payload = json.loads(CREDENTIAL_PATH.read_text(encoding="utf-8"))
    email = str(payload["email"]).strip()
    password = str(payload["password"])

    with SessionLocal() as db:
        user = auth_service.get_user_by_email(db, email)
        if user is None:
            user = auth_service.register_user(
                db,
                email=email,
                password=password,
                full_name="Research-AI staging smoke",
                workspace_name="Research-AI staging smoke",
            )
        user.email_verified_at = datetime.now(UTC)
        db.commit()

    print(f"Staging smoke account ready: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
