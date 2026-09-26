\# Backup and restore (M36)



\## Scripts



\- `scripts/backup\_db.py` — create a backup

\- `scripts/restore\_db.py` — restore a backup

\- `scripts/verify\_backup.py` — verify integrity and structure



All scripts require `pg\_dump` / `pg\_restore` / `psql` on PATH.



\## Backup



&#x20;   python scripts/backup\_db.py --format custom



Defaults:



\- Output dir: `backups/` (overridable via `BACKUP\_DIRECTORY`)

\- Format: `custom` (pg\_dump custom format)

\- Retention: `BACKUP\_RETENTION\_DAYS` (default 14)

\- Sidecar: `<file>.meta.json` with sha256, size, duration, alembic

&#x20; head at backup time, pg\_dump version



Refuses to run against local/test databases unless `--allow-test` is

passed.



\### Plain SQL



&#x20;   python scripts/backup\_db.py --format plain



\## Verify



&#x20;   python scripts/verify\_backup.py backups/research-ai-<ts>.dump



Checks:



\- Sidecar present and valid JSON

\- sha256 matches

\- Size matches

\- `pg\_restore --list` succeeds (custom format)

\- `alembic\_version` table is present in the TOC



\## Restore



&#x20;   python scripts/restore\_db.py \\

&#x20;       backups/research-ai-<ts>.dump \\

&#x20;       --target-url postgresql+psycopg://... \\

&#x20;       --yes



Safety:



\- `--dry-run` prints the command without executing

\- Refuses without `--yes`

\- Refuses if target == `DATABASE\_URL` unless `--force`



\## Object storage



Files stored on local disk (`FILE\_STORAGE\_LOCAL\_ROOT`) are NOT

included in `pg\_dump`. Back them up separately with filesystem tools

if the deployment relies on local storage.



\## RPO / RTO



Recommended:



\- Backup: nightly + before every deploy

\- Retention: 14 days minimum, 30 days in production

\- Verify: run `verify\_backup.py` after every backup

\- Restore drill: run once per quarter against a scratch database

