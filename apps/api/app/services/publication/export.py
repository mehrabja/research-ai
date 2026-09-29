"""M34 — Final publication export service.

Builds deterministic publication artifacts from the latest report state.
No external document-generation dependency is required: Markdown, HTML,
JSON, and a minimal standards-compliant DOCX package are produced with
the Python standard library.
"""
from __future__ import annotations

import html
import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models.manuscript_prose import (
    ManuscriptProseRun,
    ManuscriptProseSection,
)
from app.db.models.publication import (
    PublicationComplianceRun,
    PublicationTarget,
    PublicationTargetSelection,
)
from app.db.models.report import Report, ReportVersion


class PublicationExportValidationError(AppError):
    code = "PUBLICATION_EXPORT_VALIDATION_ERROR"
    status_code = 422
    message = "Publication export input is invalid."


SUPPORTED_FORMATS = ("markdown", "html", "json", "docx")
_FINAL_REVIEW_CHANGE_TYPES = ("humanized_post_translation", "human_review_edit")


@dataclass(frozen=True)
class PublicationExportArtifact:
    content: bytes
    filename: str
    media_type: str


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:80] or "research-report"


def _latest_final_version(
    db: Session,
    *,
    report: Report,
) -> ReportVersion | None:
    if report.status not in {"review_2", "validating", "completed"}:
        return None
    return db.execute(
        select(ReportVersion)
        .where(
            ReportVersion.report_id == report.id,
            ReportVersion.change_type.in_(_FINAL_REVIEW_CHANGE_TYPES),
        )
        .order_by(
            ReportVersion.version_number.desc(),
            ReportVersion.created_at.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def _prose_content(
    db: Session,
    *,
    report_id: uuid.UUID,
) -> tuple[str | None, uuid.UUID | None]:
    run = db.execute(
        select(ManuscriptProseRun)
        .where(
            ManuscriptProseRun.report_id == report_id,
            ManuscriptProseRun.status == "completed",
        )
        .order_by(
            ManuscriptProseRun.created_at.desc(),
            ManuscriptProseRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        return None, None

    sections = list(
        db.execute(
            select(ManuscriptProseSection)
            .where(ManuscriptProseSection.run_id == run.id)
            .order_by(ManuscriptProseSection.display_order.asc())
        ).scalars().all()
    )
    if not sections:
        return None, run.id

    blocks: list[str] = []
    for section in sections:
        title = str(section.title or section.section_key or "Section").strip()
        text = str(section.text or "").strip()
        if text:
            blocks.append(f"## {title}\n\n{text}")
        else:
            blocks.append(f"## {title}")
    return "\n\n".join(blocks).strip(), run.id


def _target(
    db: Session,
    *,
    report_id: uuid.UUID,
) -> PublicationTarget | None:
    return db.execute(
        select(PublicationTarget)
        .join(
            PublicationTargetSelection,
            PublicationTargetSelection.target_id == PublicationTarget.id,
        )
        .where(PublicationTargetSelection.report_id == report_id)
        .order_by(
            PublicationTargetSelection.created_at.desc(),
            PublicationTargetSelection.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def _compliance_run(
    db: Session,
    *,
    report_id: uuid.UUID,
) -> PublicationComplianceRun | None:
    return db.execute(
        select(PublicationComplianceRun)
        .where(
            PublicationComplianceRun.report_id == report_id,
            PublicationComplianceRun.status == "completed",
        )
        .order_by(
            PublicationComplianceRun.created_at.desc(),
            PublicationComplianceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def _metadata(
    report: Report,
    *,
    version: ReportVersion | None,
    prose_run_id: uuid.UUID | None,
    target: PublicationTarget | None,
    compliance: PublicationComplianceRun | None,
) -> dict[str, object]:
    return {
        "report_id": str(report.id),
        "topic": report.topic,
        "domain": report.domain,
        "status": report.status,
        "output_language": report.output_language,
        "version_id": str(version.id) if version else None,
        "version_number": version.version_number if version else None,
        "version_language": version.language if version else None,
        "version_change_type": version.change_type if version else None,
        "prose_run_id": str(prose_run_id) if prose_run_id else None,
        "publication_target": (
            {
                "id": str(target.id),
                "target_code": target.target_code,
                "profile_version": target.profile_version,
                "venue": target.venue,
                "venue_type": target.venue_type,
                "citation_style": target.citation_style,
                "publisher": target.publisher,
            }
            if target
            else None
        ),
        "compliance": (
            {
                "run_id": str(compliance.id),
                "gate": compliance.gate,
                "status": compliance.status,
                "finding_count": compliance.finding_count,
                "blocking_count": compliance.blocking_count,
                "error_count": compliance.error_count,
                "warning_count": compliance.warning_count,
                "target_profile_version": compliance.target_profile_version,
                "context_hash": compliance.context_hash,
            }
            if compliance
            else None
        ),
        "exported_at": datetime.now().isoformat(),
    }


def _markdown(title: str, metadata: dict[str, object], content: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Report status: {metadata['status']}",
        f"- Output language: {metadata['output_language']}",
    ]
    target = metadata.get("publication_target")
    if isinstance(target, dict):
        lines.extend(
            [
                f"- Publication target: {target['venue']}",
                f"- Citation style: {target['citation_style']}",
                f"- Target profile: {target['profile_version']}",
            ]
        )
    compliance = metadata.get("compliance")
    if isinstance(compliance, dict):
        lines.extend(
            [
                f"- Compliance gate: {compliance['gate'] or 'n/a'}",
                f"- Compliance findings: {compliance['finding_count']}",
            ]
        )
    lines.extend(["", "---", "", content.strip(), ""])
    return "\n".join(lines)


def _html_document(title: str, content: str) -> str:
    safe_title = html.escape(title)
    body_parts: list[str] = []
    for raw in content.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            body_parts.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            body_parts.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            body_parts.append(f"<h1>{html.escape(line[2:])}</h1>")
        else:
            body_parts.append(f"<p>{html.escape(line)}</p>")
    body = "\n".join(body_parts)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title>"
        "<style>body{font-family:Georgia,serif;max-width:860px;margin:48px auto;"
        "padding:0 24px;line-height:1.75;color:#20252c}h1,h2,h3{font-family:Arial,sans-serif}"
        "h1{font-size:32px;margin-bottom:28px}h2{margin-top:32px}</style></head>"
        f"<body><h1>{safe_title}</h1>{body}</body></html>"
    )


def _docx_xml(title: str, content: str) -> bytes:
    paragraphs: list[str] = []

    def paragraph(text: str, style: str | None = None) -> str:
        style_xml = (
            f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            if style
            else ""
        )
        parts = text.split("\n")
        runs: list[str] = []
        for idx, part in enumerate(parts):
            if part:
                runs.append(f"<w:r><w:t xml:space=\"preserve\">{xml_escape(part)}</w:t></w:r>")
            if idx < len(parts) - 1:
                runs.append("<w:r><w:br/></w:r>")
        return f"<w:p>{style_xml}{''.join(runs)}</w:p>"

    paragraphs.append(paragraph(title, "Title"))
    for raw in content.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            paragraphs.append(paragraph(line[4:], "Heading3"))
        elif line.startswith("## "):
            paragraphs.append(paragraph(line[3:], "Heading2"))
        elif line.startswith("# "):
            paragraphs.append(paragraph(line[2:], "Heading1"))
        else:
            paragraphs.append(paragraph(line))

    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
        "</w:sectPr></w:body></w:document>"
    ).encode()

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:qFormat/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="140" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>
</w:styles>"""

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", rels)
        package.writestr("word/document.xml", doc)
        package.writestr("word/_rels/document.xml.rels", doc_rels)
        package.writestr("word/styles.xml", styles)
    return output.getvalue()


def build_publication_export(
    db: Session,
    *,
    report: Report,
    export_format: str,
) -> PublicationExportArtifact:
    if export_format not in SUPPORTED_FORMATS:
        raise PublicationExportValidationError(
            f"unsupported export format: {export_format}"
        )

    version = _latest_final_version(db, report=report)
    prose_content, prose_run_id = _prose_content(db, report_id=report.id)
    if version is None and not prose_content:
        raise PublicationExportValidationError(
            "no finalized report content is available for export"
        )

    content = version.content.strip() if version else str(prose_content).strip()
    target = _target(db, report_id=report.id)
    compliance = _compliance_run(db, report_id=report.id)
    metadata = _metadata(
        report,
        version=version,
        prose_run_id=prose_run_id,
        target=target,
        compliance=compliance,
    )
    title = report.topic.strip() or "Research report"

    if export_format == "markdown":
        payload = _markdown(title, metadata, content).encode("utf-8")
        return PublicationExportArtifact(
            content=payload,
            filename=f"{_slug(title)}.md",
            media_type="text/markdown; charset=utf-8",
        )

    if export_format == "html":
        payload = _html_document(title, _markdown(title, metadata, content)).encode("utf-8")
        return PublicationExportArtifact(
            content=payload,
            filename=f"{_slug(title)}.html",
            media_type="text/html; charset=utf-8",
        )

    if export_format == "json":
        payload = json.dumps(
            {"metadata": metadata, "content": content},
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8")
        return PublicationExportArtifact(
            content=payload,
            filename=f"{_slug(title)}.json",
            media_type="application/json",
        )

    return PublicationExportArtifact(
        content=_docx_xml(title, _markdown(title, metadata, content)),
        filename=f"{_slug(title)}.docx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


__all__ = [
    "PublicationExportArtifact",
    "PublicationExportValidationError",
    "SUPPORTED_FORMATS",
    "build_publication_export",
]
