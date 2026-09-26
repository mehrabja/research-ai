"""M37 Phase 1 — live invariant verification."""
from __future__ import annotations

from sqlalchemy import text

from app.db.session import SessionLocal


def main() -> int:
    failures: list[str] = []
    with SessionLocal() as db:
        # 1) no orphan projects
        n = db.execute(
            text("SELECT count(*) FROM projects WHERE workspace_id IS NULL")
        ).scalar()
        print(f"orphan projects: {n} (expect 0)")
        if n != 0:
            failures.append("orphan projects")

        # 2) each workspace has exactly one active owner membership
        n = db.execute(
            text(
                "SELECT count(*) FROM ("
                " SELECT w.id FROM workspaces w"
                " LEFT JOIN workspace_memberships m"
                "   ON m.workspace_id = w.id"
                "  AND m.role = 'owner' AND m.status = 'active'"
                " GROUP BY w.id HAVING count(m.id) <> 1"
                ") t"
            )
        ).scalar()
        print(f"workspaces without exactly-one active owner: {n} (expect 0)")
        if n != 0:
            failures.append("owner count")

        # 3) workspace.owner_user_id matches active owner membership
        n = db.execute(
            text(
                "SELECT count(*) FROM workspaces w"
                " JOIN workspace_memberships m"
                "   ON m.workspace_id = w.id"
                "  AND m.role = 'owner' AND m.status = 'active'"
                " WHERE w.owner_user_id <> m.user_id"
            )
        ).scalar()
        print(f"owner_user_id mismatches: {n} (expect 0)")
        if n != 0:
            failures.append("owner mismatch")

        # 4) each workspace has exactly one live subscription
        n = db.execute(
            text(
                "SELECT count(*) FROM ("
                " SELECT w.id FROM workspaces w"
                " LEFT JOIN subscriptions s"
                "   ON s.workspace_id = w.id"
                "  AND s.status IN ('trialing','active','past_due')"
                " GROUP BY w.id HAVING count(s.id) <> 1"
                ") t"
            )
        ).scalar()
        print(f"workspaces without exactly-one live subscription: {n} (expect 0)")
        if n != 0:
            failures.append("subscription count")

        # 5) each project's workspace owner matches project.user_id
        n = db.execute(
            text(
                "SELECT count(*) FROM projects p"
                " JOIN workspace_memberships m"
                "   ON m.workspace_id = p.workspace_id"
                "  AND m.role = 'owner' AND m.status = 'active'"
                " WHERE m.user_id <> p.user_id"
            )
        ).scalar()
        print(f"projects with mismatched workspace owner: {n} (expect 0)")
        if n != 0:
            failures.append("project/workspace mismatch")

        # 6) plans seeded exactly as expected (free/pro/team)
        rows = db.execute(
            text("SELECT code FROM plans ORDER BY code")
        ).scalars().all()
        print(f"plans: {rows} (expect ['free','pro','team'])")
        if list(rows) != ["free", "pro", "team"]:
            failures.append("plans seed")

        # 7) entitlements per seeded plan = 6 features each
        n = db.execute(
            text(
                "SELECT count(*) FROM ("
                " SELECT plan_id FROM plan_entitlements"
                " GROUP BY plan_id HAVING count(*) <> 6"
                ") t"
            )
        ).scalar()
        print(f"plans without exactly-6 entitlements: {n} (expect 0)")
        if n != 0:
            failures.append("entitlements count")

        # 8) counts
        ws = db.execute(text("SELECT count(*) FROM workspaces")).scalar()
        us = db.execute(text("SELECT count(*) FROM users")).scalar()
        pj = db.execute(text("SELECT count(*) FROM projects")).scalar()
        print(f"counts: users={us} workspaces={ws} projects={pj}")

    if failures:
        print("FAIL:", ", ".join(failures))
        return 1
    print("all invariants: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())