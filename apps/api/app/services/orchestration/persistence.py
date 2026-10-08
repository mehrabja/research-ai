"""M35 — Idempotent orchestration persistence.

Checkpoints are stored on the run row; each node completion is a
durable checkpoint.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    OrchestrationBudgetExceeded,
    OrchestrationConfigurationInvalid,
    OrchestrationInvalid,
)
from app.db.models.orchestration import (
    ResearchOrchestrationNode,
    ResearchOrchestrationRun,
)
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.orchestration import (
    M35_VERSION,
    ORCHESTRATION_PLANNER_VERSION,
    ORCHESTRATION_TOOL_REGISTRY_VERSION,
    FailureClass,
    NodeStatus,
    NodeType,
    RunStatus,
    validate_node_transition,
    validate_run_transition,
)
from app.services.orchestration import budgets as budget_svc
from app.services.orchestration import context as ctx_svc
from app.services.orchestration import executor as exec_svc
from app.services.orchestration import graph as graph_svc
from app.services.orchestration import planner as plan_svc
from app.services.orchestration import policy as policy_svc
from app.services.orchestration.registry import get_tool, tool_exists

logger = logging.getLogger(__name__)


@dataclass
class PersistedRun:
    run: ResearchOrchestrationRun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"orchestration:{report_id}"},
    )


def _completed_run(
    db: Session, *, report_id: uuid.UUID, context_hash: str,
) -> ResearchOrchestrationRun | None:
    return db.execute(
        select(ResearchOrchestrationRun).where(
            ResearchOrchestrationRun.report_id == report_id,
            ResearchOrchestrationRun.context_hash == context_hash,
            ResearchOrchestrationRun.orchestration_version == M35_VERSION,
            ResearchOrchestrationRun.status == RunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID | None,
    goal: str,
    strategy: str,
    context_hash: str,
    budget: dict,
    error_message: str,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(ResearchOrchestrationRun(
                project_id=project_id,
                report_id=report_id,
                user_id=user_id,
                goal=goal,
                context_hash=context_hash,
                orchestration_version=M35_VERSION,
                planner_version=ORCHESTRATION_PLANNER_VERSION,
                tool_registry_version=ORCHESTRATION_TOOL_REGISTRY_VERSION,
                strategy=strategy,
                status=RunStatus.FAILED.value,
                budget=budget,
                error_message=error_message[:500],
                failed_at=now,
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m35_failed_run_audit_failed")


def _materialize_nodes(
    db: Session,
    *,
    run: ResearchOrchestrationRun,
    plan: plan_svc.Plan,
) -> list[ResearchOrchestrationNode]:
    rows: list[ResearchOrchestrationNode] = []
    for planned in plan.nodes:
        if not tool_exists(planned.node_key):
            raise OrchestrationInvalid(
                f"unknown tool in plan: {planned.node_key}"
            )
        tool_spec, _tool_fn = get_tool(planned.node_key)
        node_type = (
            NodeType.DETERMINISTIC.value
            if tool_spec.deterministic
            else NodeType.MODEL_ASSISTED.value
        )
        node_ctx_hash = ctx_svc.compute_node_context_hash(
            run_context_hash=run.context_hash,
            node_key=planned.node_key,
            node_version=ORCHESTRATION_TOOL_REGISTRY_VERSION,
            payload=planned.payload,
        )
        node = ResearchOrchestrationNode(
            run_id=run.id,
            project_id=run.project_id,
            report_id=run.report_id,
            node_key=planned.node_key,
            node_version=ORCHESTRATION_TOOL_REGISTRY_VERSION,
            node_type=node_type,
            sequence=planned.sequence,
            depends_on=list(planned.depends_on),
            status=NodeStatus.PENDING.value,
            input_snapshot=planned.payload,
            context_hash=node_ctx_hash,
            attempt=0,
            max_attempts=tool_spec.max_attempts,
            deterministic=tool_spec.deterministic,
        )
        db.add(node)
        rows.append(node)
    db.flush()
    return rows


def run_m35_persisted(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID | None,
    goal: str,
    strategy: str,
    payload: dict | None = None,
    force: bool = False,
    commit: bool = True,
) -> PersistedRun:
    settings = get_settings()
    if not settings.orchestration_enabled:
        raise OrchestrationConfigurationInvalid(
            "orchestration is disabled"
        )

    report = db.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise OrchestrationInvalid("report does not belong to project")

    budget = budget_svc.effective_budget(settings)

    context_hash: str | None = None
    run: ResearchOrchestrationRun | None = None
    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m35_context_hash(
            db,
            project_id=project_id,
            report_id=report_id,
            goal=goal,
            strategy=strategy,
            budget=budget,
        )

        existing = _completed_run(
            db, report_id=report_id, context_hash=context_hash,
        )
        if existing is not None:
            return PersistedRun(run=existing, skipped=True)

        now = datetime.now(UTC)
        run = ResearchOrchestrationRun(
            project_id=project_id,
            report_id=report_id,
            user_id=user_id,
            goal=goal,
            goal_meta=dict(payload or {}),
            context_hash=context_hash,
            orchestration_version=M35_VERSION,
            planner_version=ORCHESTRATION_PLANNER_VERSION,
            tool_registry_version=ORCHESTRATION_TOOL_REGISTRY_VERSION,
            strategy=strategy,
            status=RunStatus.PLANNING.value,
            budget=budget,
            budget_used={
                "provider_calls": 0,
                "tokens": 0,
                "evidence_volume": 0,
                "generated_chars": 0,
            },
            node_count=0,
            completed_node_count=0,
            failed_node_count=0,
            started_at=now,
        )
        db.add(run)
        db.flush()

        plan = plan_svc.plan_orchestration(
            goal=goal,
            strategy=strategy,
            payload=payload,
            max_nodes=int(budget["max_nodes"]),
        )
        nodes = _materialize_nodes(db, run=run, plan=plan)
        run.node_count = len(nodes)

        validate_run_transition(run.status, RunStatus.EXECUTING.value)
        run.status = RunStatus.EXECUTING.value
        db.flush()

        if commit:
            # Make the run and its pending nodes visible before the first
            # provider call. This allows pause/cancel/approval controls to
            # operate against a durable run while work is executing.
            db.commit()
            db.refresh(run)

        _execute_all(
            db,
            run=run,
            nodes=nodes,
            checkpoint_commit=commit,
        )

        if run.status != RunStatus.EXECUTING.value:
            if commit:
                db.commit()
                db.refresh(run)
            else:
                db.flush()
            return PersistedRun(run=run, skipped=False)

        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now(UTC)
        run.duration_ms = int(
            (run.completed_at - run.started_at).total_seconds() * 1000
        ) if run.started_at else None

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedRun(run=run, skipped=False)

    except Exception as exc:
        logger.exception("orchestration_persist_failed")
        if commit and run is not None and run.id:
            try:
                with SessionLocal() as s:
                    persisted_run = s.get(
                        ResearchOrchestrationRun, run.id,
                    )
                    if persisted_run is not None and not (
                        persisted_run.status
                        in (
                            RunStatus.CANCELLED.value,
                            RunStatus.COMPLETED.value,
                            RunStatus.FAILED.value,
                        )
                    ):
                        persisted_run.status = RunStatus.FAILED.value
                        persisted_run.error_message = str(exc)[:500]
                        persisted_run.failed_at = datetime.now(UTC)
                        s.commit()
            except Exception:
                logger.exception("m35_existing_failure_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m35_rollback_failed")
        if context_hash is not None:
            _persist_failed_run(
                project_id=project_id,
                report_id=report_id,
                user_id=user_id,
                goal=goal,
                strategy=strategy,
                context_hash=context_hash,
                budget=budget,
                error_message=str(exc),
            )
        raise


def _checkpoint(
    db: Session,
    *,
    run: ResearchOrchestrationRun,
    commit: bool,
) -> None:
    if commit:
        db.commit()
        db.refresh(run)
    else:
        db.flush()


def _execute_all(
    db: Session,
    *,
    run: ResearchOrchestrationRun,
    nodes: list[ResearchOrchestrationNode],
    checkpoint_commit: bool = False,
) -> None:
    completed: set[str] = {
        n.node_key for n in nodes
        if n.status == NodeStatus.COMPLETED.value
    }
    ordered: list[tuple[str, list[str]]] = [
        (n.node_key, list(n.depends_on or [])) for n in nodes
    ]
    node_by_key = {n.node_key: n for n in nodes}
    guard = 0
    max_guard = max(1, len(nodes)) * 4

    while len(completed) < len(nodes):
        db.refresh(run)
        if run.status != RunStatus.EXECUTING.value:
            return

        guard += 1
        if guard > max_guard:
            raise OrchestrationInvalid(
                "orchestration scheduler did not make progress"
            )

        eligible = graph_svc.successors_of(
            all_nodes=ordered,
            completed=completed,
        )
        if not eligible:
            raise OrchestrationInvalid(
                "orchestration has no eligible node"
            )

        key = eligible[0]
        node = node_by_key[key]

        try:
            _execute_one(db, run=run, node=node)
        except OrchestrationBudgetExceeded as exc:
            validate_run_transition(
                run.status, RunStatus.BLOCKED.value,
            )
            run.status = RunStatus.BLOCKED.value
            run.current_node_key = key
            run.error_message = str(exc)[:500]
            run.checkpoint_state = {
                "completed": sorted(completed),
                "blocked": key,
            }
            run.last_checkpoint_at = datetime.now(UTC)
            _checkpoint(
                db, run=run, commit=checkpoint_commit,
            )
            return

        if node.status == NodeStatus.AWAITING_APPROVAL.value:
            validate_run_transition(
                run.status, RunStatus.AWAITING_APPROVAL.value,
            )
            run.status = RunStatus.AWAITING_APPROVAL.value
            run.current_node_key = key
            required = list(run.approvals_required or [])
            if key not in required:
                required.append(key)
            run.approvals_required = required
            run.checkpoint_state = {
                "completed": sorted(completed),
                "awaiting_approval": key,
            }
            run.last_checkpoint_at = datetime.now(UTC)
            _checkpoint(
                db, run=run, commit=checkpoint_commit,
            )
            return

        if node.status == NodeStatus.COMPLETED.value:
            if key not in completed:
                completed.add(key)
                run.completed_node_count += 1
        elif node.status == NodeStatus.FAILED.value:
            run.failed_node_count += 1
            run.errors = list(run.errors or []) + [{
                "node_key": node.node_key,
                "error_class": node.error_class,
                "error_message": node.error_message,
            }]
            validate_run_transition(
                run.status, RunStatus.FAILED.value,
            )
            run.status = RunStatus.FAILED.value
            run.failed_at = datetime.now(UTC)
            run.current_node_key = key
            run.checkpoint_state = {
                "completed": sorted(completed),
                "failed": key,
            }
            _checkpoint(
                db, run=run, commit=checkpoint_commit,
            )
            return

        # A control route may have paused/cancelled the durable run while
        # the provider call was in flight. Persist this node, but never
        # overwrite the externally requested terminal/control state.
        db.refresh(run)
        run.current_node_key = key
        run.checkpoint_state = {
            "completed": sorted(completed),
            "current": key,
        }
        run.last_checkpoint_at = datetime.now(UTC)
        _checkpoint(
            db, run=run, commit=checkpoint_commit,
        )

        if run.status != RunStatus.EXECUTING.value:
            return



def _execute_one(
    db: Session,
    *,
    run: ResearchOrchestrationRun,
    node: ResearchOrchestrationNode,
    approval_granted: bool = False,
) -> None:
    if approval_granted:
        validate_node_transition(
            node.status, NodeStatus.RUNNING.value,
        )
        node.status = NodeStatus.RUNNING.value
    else:
        decision = policy_svc.evaluate_node_policy(
            node_key=node.node_key,
            node_type=node.node_type,
            deterministic=node.deterministic,
        )
        if decision.approval_required:
            validate_node_transition(
                node.status, NodeStatus.AWAITING_APPROVAL.value,
            )
            node.status = NodeStatus.AWAITING_APPROVAL.value
            db.flush()
            return
        validate_node_transition(
            node.status, NodeStatus.RUNNING.value,
        )
        node.status = NodeStatus.RUNNING.value

    node.started_at = datetime.now(UTC)
    node.attempt += 1

    check = budget_svc.check_before_node(
        budget=run.budget,
        used=run.budget_used,
        node_count=run.completed_node_count,
    )
    if not check.ok:
        node.status = NodeStatus.BLOCKED.value
        node.error_class = FailureClass.BUDGET_EXCEEDED.value
        node.error_message = check.reason
        db.flush()
        raise OrchestrationBudgetExceeded(check.reason or "budget")

    try:
        out = exec_svc.execute_node(
            db,
            node_key=node.node_key,
            project_id=run.project_id,
            report_id=run.report_id,
            user_id=run.user_id,
            run_id=run.id,
            node_id=node.id,
            payload=dict(node.input_snapshot or {}),
        )
    except Exception as exc:
        node.status = NodeStatus.FAILED.value
        node.error_class = FailureClass.INTERNAL.value
        node.error_message = str(exc)[:500]
        db.flush()
        return

    node.output_snapshot = out
    node.status = NodeStatus.COMPLETED.value
    node.completed_at = datetime.now(UTC)
    node.duration_ms = int(out.get("_duration_ms", 0))
    db.flush()


def resume_m35_persisted(
    db: Session,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    node_id: uuid.UUID,
    commit: bool = True,
) -> PersistedRun:
    run = db.execute(
        select(ResearchOrchestrationRun)
        .where(
            ResearchOrchestrationRun.id == run_id,
            ResearchOrchestrationRun.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if run is None:
        raise OrchestrationInvalid("orchestration run not found")
    if run.status != RunStatus.AWAITING_APPROVAL.value:
        raise OrchestrationInvalid(
            f"run is not awaiting approval: {run.status!r}"
        )

    _lock_report(db, report_id=run.report_id)
    node = db.execute(
        select(ResearchOrchestrationNode)
        .where(
            ResearchOrchestrationNode.id == node_id,
            ResearchOrchestrationNode.run_id == run.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if node is None:
        raise OrchestrationInvalid("orchestration node not found")
    if node.status != NodeStatus.AWAITING_APPROVAL.value:
        raise OrchestrationInvalid(
            f"node is not awaiting approval: {node.status!r}"
        )

    validate_run_transition(
        run.status, RunStatus.EXECUTING.value,
    )
    run.status = RunStatus.EXECUTING.value

    required = list(run.approvals_required or [])
    received = list(run.approvals_received or [])
    if node.node_key not in received:
        received.append(node.node_key)
    run.approvals_received = received
    if node.node_key in required:
        required.remove(node.node_key)
    run.approvals_required = required

    nodes = list(
        db.execute(
            select(ResearchOrchestrationNode)
            .where(ResearchOrchestrationNode.run_id == run.id)
            .order_by(ResearchOrchestrationNode.sequence.asc())
        ).scalars().all()
    )
    completed_before = {
        n.node_key for n in nodes if n.status == NodeStatus.COMPLETED.value
    }
    approved_key = node.node_key

    ordered = [(n.node_key, list(n.depends_on or [])) for n in nodes]
    node_by_key = {n.node_key: n for n in nodes}
    guard = 0
    max_guard = max(1, len(nodes)) * 4

    while len(completed_before) < len(nodes):
        guard += 1
        if guard > max_guard:
            raise OrchestrationInvalid(
                "orchestration scheduler did not make progress during resume"
            )
        eligible = graph_svc.successors_of(
            all_nodes=ordered, completed=completed_before,
        )
        if not eligible:
            raise OrchestrationInvalid(
                "orchestration has no eligible node during resume"
            )
        key = eligible[0]
        current = node_by_key[key]
        _execute_one(
            db,
            run=run,
            node=current,
            approval_granted=(key == approved_key),
        )
        if current.status == NodeStatus.AWAITING_APPROVAL.value:
            run.status = RunStatus.AWAITING_APPROVAL.value
            run.current_node_key = key
            required = list(run.approvals_required or [])
            if key not in required:
                required.append(key)
            run.approvals_required = required
            run.checkpoint_state = {
                "completed": sorted(completed_before),
                "awaiting_approval": key,
            }
            run.last_checkpoint_at = datetime.now(UTC)
            break
        if current.status == NodeStatus.FAILED.value:
            run.failed_node_count += 1
            run.errors = list(run.errors or []) + [{
                "node_key": current.node_key,
                "error_class": current.error_class,
                "error_message": current.error_message,
            }]
            validate_run_transition(
                run.status, RunStatus.FAILED.value,
            )
            run.status = RunStatus.FAILED.value
            run.failed_at = datetime.now(UTC)
            break
        if key not in completed_before:
            completed_before.add(key)
            run.completed_node_count += 1
        run.current_node_key = key
        run.checkpoint_state = {
            "completed": sorted(completed_before),
            "current": key,
        }
        run.last_checkpoint_at = datetime.now(UTC)

    if len(completed_before) == len(nodes):
        validate_run_transition(
            run.status, RunStatus.COMPLETED.value,
        )
        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now(UTC)
        if run.started_at is not None:
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )

    if commit:
        db.commit()
        db.refresh(run)
    else:
        db.flush()
    return PersistedRun(run=run, skipped=False)



def resume_paused_m35_persisted(
    db: Session,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    commit: bool = True,
) -> PersistedRun:
    run = db.execute(
        select(ResearchOrchestrationRun)
        .where(
            ResearchOrchestrationRun.id == run_id,
            ResearchOrchestrationRun.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if run is None:
        raise OrchestrationInvalid("orchestration run not found")
    if run.status != RunStatus.PAUSED.value:
        raise OrchestrationInvalid(
            f"run is not paused: {run.status!r}"
        )

    _lock_report(db, report_id=run.report_id)
    validate_run_transition(
        run.status, RunStatus.EXECUTING.value,
    )
    run.status = RunStatus.EXECUTING.value
    run.cancelled_at = None

    nodes = list(
        db.execute(
            select(ResearchOrchestrationNode)
            .where(ResearchOrchestrationNode.run_id == run.id)
            .order_by(ResearchOrchestrationNode.sequence.asc())
        ).scalars().all()
    )
    completed = {
        n.node_key for n in nodes if n.status == NodeStatus.COMPLETED.value
    }
    ordered = [(n.node_key, list(n.depends_on or [])) for n in nodes]
    node_by_key = {n.node_key: n for n in nodes}
    guard = 0
    max_guard = max(1, len(nodes)) * 4

    while len(completed) < len(nodes):
        guard += 1
        if guard > max_guard:
            raise OrchestrationInvalid(
                "orchestration scheduler did not make progress during resume"
            )
        eligible = graph_svc.successors_of(
            all_nodes=ordered, completed=completed,
        )
        if not eligible:
            raise OrchestrationInvalid(
                "orchestration has no eligible node during resume"
            )
        key = eligible[0]
        node = node_by_key[key]
        _execute_one(
            db,
            run=run,
            node=node,
            approval_granted=False,
        )
        if node.status == NodeStatus.AWAITING_APPROVAL.value:
            run.status = RunStatus.AWAITING_APPROVAL.value
            run.current_node_key = key
            required = list(run.approvals_required or [])
            if key not in required:
                required.append(key)
            run.approvals_required = required
            run.checkpoint_state = {
                "completed": sorted(completed),
                "awaiting_approval": key,
            }
            run.last_checkpoint_at = datetime.now(UTC)
            break
        if node.status == NodeStatus.FAILED.value:
            run.failed_node_count += 1
            run.errors = list(run.errors or []) + [{
                "node_key": node.node_key,
                "error_class": node.error_class,
                "error_message": node.error_message,
            }]
            validate_run_transition(
                run.status, RunStatus.FAILED.value,
            )
            run.status = RunStatus.FAILED.value
            run.failed_at = datetime.now(UTC)
            break
        completed.add(key)
        run.completed_node_count += 1
        run.current_node_key = key
        run.checkpoint_state = {
            "completed": sorted(completed),
            "current": key,
        }
        run.last_checkpoint_at = datetime.now(UTC)

    if len(completed) == len(nodes):
        validate_run_transition(
            run.status, RunStatus.COMPLETED.value,
        )
        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now(UTC)
        if run.started_at is not None:
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )

    if commit:
        db.commit()
        db.refresh(run)
    else:
        db.flush()
    return PersistedRun(run=run, skipped=False)


__all__ = ["PersistedRun", "resume_m35_persisted", "resume_paused_m35_persisted", "run_m35_persisted"]
