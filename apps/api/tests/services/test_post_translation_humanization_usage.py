"""M17 — Real usage recording test."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.humanization import (
    HumanizationIteration,
    HumanizationRewrite,
    HumanizationRun,
)
from app.db.models.ops import UsageLog
from app.db.models.pipeline import (
    DetectionRun,
    DetectionSegment,
    TranslationRun,
    TranslationVersion,
)
from app.db.models.report import (
    Report,
    ReportEvent,
    ReportVersion,
    ReviewEvent,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.humanization import default_post_translation_policy
from app.services import post_translation_humanization as m17
from app.services import report_versions as version_service
from app.services.usage import record_humanization_usage


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        report_ids = select(Report.id).where(Report.user_id.in_(user_ids))
        hrun_ids = select(HumanizationRun.id).where(
            HumanizationRun.report_id.in_(report_ids)
        )
        det_ids = select(DetectionRun.id).where(
            DetectionRun.report_id.in_(report_ids)
        )
        trun_ids = select(TranslationRun.id).where(
            TranslationRun.report_id.in_(report_ids)
        )
        db.execute(
            delete(HumanizationRewrite).where(
                HumanizationRewrite.humanization_run_id.in_(hrun_ids)
            )
        )
        db.execute(
            delete(HumanizationIteration).where(
                HumanizationIteration.humanization_run_id.in_(hrun_ids)
            )
        )
        db.execute(
            delete(HumanizationRun).where(
                HumanizationRun.report_id.in_(report_ids)
            )
        )
        db.execute(
            delete(DetectionSegment).where(
                DetectionSegment.detection_run_id.in_(det_ids)
            )
        )
        db.execute(
            delete(DetectionRun).where(
                DetectionRun.report_id.in_(report_ids)
            )
        )
        db.execute(
            delete(UsageLog).where(UsageLog.report_id.in_(report_ids))
        )
        db.execute(
            delete(TranslationVersion).where(
                TranslationVersion.translation_run_id.in_(trun_ids)
            )
        )
        db.execute(
            delete(TranslationRun).where(
                TranslationRun.report_id.in_(report_ids)
            )
        )
        db.execute(
            delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportVersion).where(
                ReportVersion.report_id.in_(report_ids)
            )
        )
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _seed(uid):
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="T",
            output_language="fa",
            status="post_translation_review",
        )
        db.add(report)
        db.flush()
        v = ReportVersion(
            report_id=report.id,
            version_number=1,
            language="en",
            content="Line1 [E1].\n\nLine2.\n\nLine3.",
            created_by_user=False,
            change_type="humanized",
        )
        db.add(v)
        db.flush()
        db.add(
            ReviewEvent(
                report_id=report.id,
                stage="pre_translation",
                user_id=uid,
                action="approved",
                version_id=v.id,
                notes=None,
            )
        )
        db.flush()
        trun = TranslationRun(
            report_id=report.id,
            generation_run_id=None,
            source_version_id=v.id,
            profile_id="openai/x:test",
            source_lang="en",
            target_lang="fa",
            provider="fake",
            status="success",
        )
        db.add(trun)
        db.flush()
        tver = TranslationVersion(
            translation_run_id=trun.id,
            content="خط1 [E1].\n\nخط2.\n\nخط3.",
            preservation_check_status="passed",
            preservation_details={},
        )
        db.add(tver)
        db.commit()
        return report.id, trun.id, tver.id


class _DetProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def detect(self, *, text):
        class R:
            pass

        r = R()
        r.probability = 0.8
        r.label = "high"
        r.provider = "fake"
        r.model = "fake-model"
        r.details = {
            "segments": [
                {
                    "paragraph_index": 0,
                    "segment_identifier": "p0",
                    "flagged": True,
                    "score": 0.9,
                    "reason": "ai_like",
                },
                {
                    "paragraph_index": 1,
                    "segment_identifier": "p1",
                    "flagged": False,
                    "score": 0.1,
                    "reason": None,
                },
                {
                    "paragraph_index": 2,
                    "segment_identifier": "p2",
                    "flagged": False,
                    "score": 0.1,
                    "reason": None,
                },
            ]
        }
        return r


class _DetProfile:
    profile_id = "fake/det:test"
    minimum_text_chars = 10


class _GenProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.calls = 0

    def generate(self, **kw):
        self.calls += 1

        class R:
            pass

        r = R()
        r.text = "خط1 بازنویسی [E1]."
        r.input_tokens = 120
        r.output_tokens = 80
        r.provider = self.provider_name
        r.model = self.model_name
        return r


def test_real_usage_recording(cleanup_users):
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"u-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)

    report_id, trun_id, tver_id = _seed(uid)
    provider = _GenProvider()

    out = m17.run_post_translation_humanization(
        db=SessionLocal(),
        user_id=uid,
        report_id=report_id,
        translation_run_id=trun_id,
        translation_version_id=tver_id,
        provider=provider,
        detection_provider=_DetProvider(),
        detection_profile=_DetProfile(),
        policy=default_post_translation_policy(job_id="j1"),
        version_service=version_service,
        usage_recorder=record_humanization_usage,
    )
    assert out.status == "success"
    assert provider.calls == 1

    with SessionLocal() as db:
        usages = db.execute(
            select(UsageLog).where(
                UsageLog.report_id == report_id,
                UsageLog.phase == "humanization",
            )
        ).scalars().all()
        assert len(usages) >= 1
        u = usages[-1]
        assert u.provider == "fake"
        assert u.input_tokens == 120
        assert u.output_tokens == 80
        assert u.idempotency_key

        hr = db.get(HumanizationRun, out.run_id)
        assert hr.tokens_used == 200
        assert hr.policy_json.get("cumulative_input_tokens") == 120
        assert hr.policy_json.get("cumulative_output_tokens") == 80
