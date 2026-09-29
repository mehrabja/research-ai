from __future__ import annotations

import io
import json
import uuid
import zipfile
from types import SimpleNamespace

import pytest

from app.services.publication import export as pub_export


def _report() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        topic="Deterministic publication export",
        domain="computer_science",
        status="review_2",
        output_language="en",
    )


def _version() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        version_number=3,
        language="en",
        change_type="human_review_edit",
        content="# Abstract\n\nFinal reviewed manuscript content.",
    )


def _target() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        target_code="demo-journal",
        profile_version="v1",
        venue="Demo Journal",
        venue_type="journal",
        citation_style="apa",
        publisher="Demo Publisher",
    )


def _compliance() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        gate="passed",
        status="completed",
        finding_count=2,
        blocking_count=0,
        error_count=0,
        warning_count=2,
        target_profile_version="v1",
        context_hash="abc123",
    )


@pytest.mark.parametrize(
    ("export_format", "suffix", "media_type"),
    [
        ("markdown", ".md", "text/markdown; charset=utf-8"),
        ("html", ".html", "text/html; charset=utf-8"),
        ("json", ".json", "application/json"),
        (
            "docx",
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_build_publication_export_supports_all_formats(
    monkeypatch: pytest.MonkeyPatch,
    export_format: str,
    suffix: str,
    media_type: str,
) -> None:
    report = _report()
    version = _version()

    monkeypatch.setattr(
        pub_export,
        "_latest_final_version",
        lambda db, report: version,
    )
    monkeypatch.setattr(
        pub_export,
        "_prose_content",
        lambda db, report_id: (None, None),
    )
    monkeypatch.setattr(
        pub_export,
        "_target",
        lambda db, report_id: _target(),
    )
    monkeypatch.setattr(
        pub_export,
        "_compliance_run",
        lambda db, report_id: _compliance(),
    )

    artifact = pub_export.build_publication_export(
        object(),
        report=report,
        export_format=export_format,
    )

    assert artifact.filename.endswith(suffix)
    assert artifact.media_type == media_type
    assert len(artifact.content) > 0

    if export_format == "markdown":
        text = artifact.content.decode("utf-8")
        assert "# Deterministic publication export" in text
        assert "Demo Journal" in text
        assert "Compliance gate: passed" in text
    elif export_format == "html":
        text = artifact.content.decode("utf-8")
        assert "<!doctype html>" in text
        assert "<h1>Deterministic publication export</h1>" in text
        assert "Final reviewed manuscript content." in text
    elif export_format == "json":
        payload = json.loads(artifact.content)
        assert payload["metadata"]["publication_target"]["venue"] == "Demo Journal"
        assert payload["metadata"]["compliance"]["finding_count"] == 2
        assert payload["content"] == "# Abstract\n\nFinal reviewed manuscript content."
    else:
        with zipfile.ZipFile(io.BytesIO(artifact.content)) as package:
            assert "word/document.xml" in package.namelist()
            assert "word/styles.xml" in package.namelist()
            document = package.read("word/document.xml").decode("utf-8")
        assert "Deterministic publication export" in document
        assert "Final reviewed manuscript content." in document


def test_build_publication_export_falls_back_to_latest_completed_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report()
    monkeypatch.setattr(
        pub_export,
        "_latest_final_version",
        lambda db, report: None,
    )
    monkeypatch.setattr(
        pub_export,
        "_prose_content",
        lambda db, report_id: ("## Results\n\nCompleted prose output.", uuid.uuid4()),
    )
    monkeypatch.setattr(pub_export, "_target", lambda db, report_id: None)
    monkeypatch.setattr(pub_export, "_compliance_run", lambda db, report_id: None)

    artifact = pub_export.build_publication_export(
        object(),
        report=report,
        export_format="markdown",
    )

    text = artifact.content.decode("utf-8")
    assert "Completed prose output." in text
    assert "prose_run_id" not in text


def test_build_publication_export_rejects_unknown_format() -> None:
    with pytest.raises(pub_export.PublicationExportValidationError):
        pub_export.build_publication_export(
            object(),
            report=_report(),
            export_format="pdf",
        )


def test_build_publication_export_rejects_missing_content(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    monkeypatch.setattr(pub_export, "_latest_final_version", lambda db, report: None)
    monkeypatch.setattr(pub_export, "_prose_content", lambda db, report_id: (None, None))

    with pytest.raises(pub_export.PublicationExportValidationError, match="no finalized report content"):
        pub_export.build_publication_export(
            object(),
            report=report,
            export_format="markdown",
        )
