"""M16 — Translation worker handler tests."""
from __future__ import annotations

import uuid

import pytest


def test_translate_report_registered():
    from app.workers.handlers import register_all_handlers
    from app.workers.registry import registered_types

    register_all_handlers()
    assert "translate_report" in registered_types()


def test_invalid_payload_rejected():
    from app.domain.jobs import JobContext, JobTypes
    from app.workers.handlers import (
        InvalidTranslationPayloadError,
        _translate_report,
    )

    ctx = JobContext(
        job_id=uuid.uuid4(),
        job_type=JobTypes.TRANSLATE_REPORT.value,
        attempt_count=0,
        worker_id="test",
        payload={},  # missing required fields
    )
    with pytest.raises(InvalidTranslationPayloadError):
        _translate_report(ctx)


def test_translate_report_job_type_exists():
    from app.domain.jobs import EXECUTABLE_JOB_TYPES, JobTypes

    assert JobTypes.TRANSLATE_REPORT.value in EXECUTABLE_JOB_TYPES
    assert JobTypes.TRANSLATE_REPORT.value == "translate_report"
