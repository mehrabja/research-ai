"""M20 — Code Intelligence service.

Concurrency: for each ``project_file_id`` there is at most one
``CodeAnalysis``. Re-runs acquire a row lock via ``SELECT ... FOR UPDATE``
and the first-run race on the unique constraint is recovered by
re-locking the winner.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    CodeAnalysisResourceLimit,
    CodeAnalysisUnsupportedLanguage,
    FileNotFound,
)
from app.db.models.code_analysis import (
    CodeAnalysis,
    CodeDependency,
    CodeSymbol,
)
from app.db.models.project_file import ProjectFile
from app.domain.code_intelligence import (
    Language,
    LanguageSupport,
    ParseStatus,
    detect_language,
    language_support,
)
from app.services.parsers import parse_source

logger = logging.getLogger(__name__)


def _read_bounded(
    chunks: Iterator[bytes], max_bytes: int
) -> tuple[str, bool]:
    buf = bytearray()
    for c in chunks:
        buf.extend(c)
        if len(buf) > max_bytes:
            return "", True
    try:
        return buf.decode("utf-8"), False
    except UnicodeDecodeError:
        return buf.decode("utf-8", errors="replace"), False


def _get_or_create_parent_locked(
    db: Session, *, project_file_id: uuid.UUID
) -> CodeAnalysis:
    existing = db.execute(
        select(CodeAnalysis)
        .where(CodeAnalysis.project_file_id == project_file_id)
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    settings = get_settings()
    placeholder = CodeAnalysis(
        project_file_id=project_file_id,
        language=Language.UNKNOWN.value,
        parser="pending",
        parser_version="pending",
        analysis_version=settings.intelligence_analysis_version,
        parse_status=ParseStatus.PENDING.value,
    )
    db.add(placeholder)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = db.execute(
            select(CodeAnalysis)
            .where(CodeAnalysis.project_file_id == project_file_id)
            .with_for_update()
        ).scalar_one()
        return winner
    return placeholder


def analyze_file(
    db: Session,
    *,
    project_file_id: uuid.UUID,
    chunks: Iterator[bytes],
) -> CodeAnalysis:
    settings = get_settings()
    pf = db.get(ProjectFile, project_file_id)
    if pf is None:
        raise FileNotFound()

    language = detect_language(pf.extension)
    support = language_support(language)
    if support is LanguageSupport.UNSUPPORTED:
        raise CodeAnalysisUnsupportedLanguage(
            f"language {language.value!r} is not analyzable"
        )

    # --- Parse phase (no DB writes) -------------------------------------
    source, too_large = _read_bounded(
        chunks, settings.code_max_source_bytes
    )
    if too_large:
        raise CodeAnalysisResourceLimit(
            "source exceeds code_max_source_bytes"
        )
    result = parse_source(source=source, language=language)

    status = (
        ParseStatus.COMPLETED.value
        if result.supported and result.error is None
        else ParseStatus.FAILED.value
        if result.error is not None
        else ParseStatus.UNSUPPORTED.value
    )

    symbols = result.symbols[: settings.code_max_symbols]
    deps = result.dependencies[: settings.code_max_dependencies]

    # --- DB phase (locked) ----------------------------------------------
    analysis = _get_or_create_parent_locked(
        db, project_file_id=project_file_id
    )

    db.execute(
        delete(CodeSymbol).where(
            CodeSymbol.code_analysis_id == analysis.id
        )
    )
    db.execute(
        delete(CodeDependency).where(
            CodeDependency.code_analysis_id == analysis.id
        )
    )

    analysis.language = language.value
    analysis.parser = result.parser
    analysis.parser_version = result.parser_version
    analysis.analysis_version = settings.intelligence_analysis_version
    analysis.parse_status = status
    analysis.parse_error = result.error[:500] if result.error else None
    analysis.line_count = result.line_count
    analysis.character_count = result.character_count
    analysis.symbol_count = len(symbols)
    analysis.function_count = sum(
        1 for s in symbols if s.symbol_type in ("function", "method")
    )
    analysis.class_count = sum(
        1 for s in symbols if s.symbol_type == "class"
    )
    analysis.import_count = len(deps)
    analysis.complexity_score = result.complexity_score
    analysis.analysis_meta = {
        "module_docstring": result.module_docstring,
        "language_support": support.value,
    }
    analysis.updated_at = datetime.now(UTC)
    db.flush()

    for s in symbols:
        db.add(
            CodeSymbol(
                code_analysis_id=analysis.id,
                symbol_type=s.symbol_type,
                name=s.name,
                qualified_name=s.qualified_name,
                parent_name=s.parent_name,
                line_start=s.line_start,
                line_end=s.line_end,
                column_start=s.column_start,
                column_end=s.column_end,
                signature=s.signature,
                docstring=s.docstring,
                symbol_meta=s.meta,
            )
        )
    for d in deps:
        db.add(
            CodeDependency(
                code_analysis_id=analysis.id,
                dependency_name=d.dependency_name[:500],
                dependency_type=d.dependency_type,
                line_number=d.line_number,
                is_relative=d.is_relative,
                dependency_meta=d.meta,
            )
        )
    db.commit()
    db.refresh(analysis)
    return analysis


def get_analysis(
    db: Session, *, user_id: uuid.UUID, file_id: uuid.UUID
) -> CodeAnalysis | None:
    from app.services.files import get_file

    get_file(db, user_id=user_id, file_id=file_id)
    return db.execute(
        select(CodeAnalysis).where(
            CodeAnalysis.project_file_id == file_id
        )
    ).scalar_one_or_none()


def list_symbols(
    db: Session,
    *,
    analysis_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[CodeSymbol], int]:
    from sqlalchemy import func

    base = select(CodeSymbol).where(
        CodeSymbol.code_analysis_id == analysis_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(
                CodeSymbol.line_start.asc(), CodeSymbol.id.asc()
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def list_dependencies(
    db: Session,
    *,
    analysis_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[CodeDependency], int]:
    from sqlalchemy import func

    base = select(CodeDependency).where(
        CodeDependency.code_analysis_id == analysis_id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(
                CodeDependency.line_number.asc().nullslast(),
                CodeDependency.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total
