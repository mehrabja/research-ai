#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

cd "$(dirname "$0")/../apps/api"

python - <<'PY'
import os
from sqlalchemy import create_engine, select
from app.db.models.jobs import Job

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as connection:
    stale = connection.execute(
        select(Job.id).where(Job.status == "processing").limit(1)
    ).scalar_one_or_none()
print(f"stale_candidate={stale!s}")
PY

echo "Run the staging failure-injection suite separately; this script only checks DB access."
