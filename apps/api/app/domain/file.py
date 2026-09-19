"""M19 — File domain (pure: no SQLAlchemy / FastAPI / httpx)."""
from __future__ import annotations

import re
import uuid
from enum import StrEnum


class FileStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class ExtractionStatus(StrEnum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_SUPPORTED = "not_supported"


class FileKind(StrEnum):
    DOCUMENT = "document"
    PDF = "pdf"
    IMAGE = "image"
    ARCHIVE = "archive"
    TEXT = "text"
    CODE = "code"
    STRUCTURED_DATA = "structured_data"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    UNKNOWN = "unknown"


ALL_FILE_STATUSES: tuple[str, ...] = tuple(s.value for s in FileStatus)
ALL_FILE_KINDS: tuple[str, ...] = tuple(k.value for k in FileKind)
ALL_EXTRACTION_STATUSES: tuple[str, ...] = tuple(
    s.value for s in ExtractionStatus
)

_PROCESSING_TERMINAL: frozenset[str] = frozenset({FileStatus.FAILED.value})
_ABSOLUTE_TERMINAL: frozenset[str] = frozenset({FileStatus.DELETED.value})

_ALLOWED_FILE_TRANSITIONS: dict[str, frozenset[str]] = {
    FileStatus.UPLOADED.value: frozenset({
        FileStatus.PROCESSING.value,
        FileStatus.READY.value,
        FileStatus.FAILED.value,
        FileStatus.DELETED.value,
    }),
    FileStatus.PROCESSING.value: frozenset({
        FileStatus.READY.value,
        FileStatus.FAILED.value,
        FileStatus.DELETED.value,
    }),
    FileStatus.READY.value: frozenset({FileStatus.DELETED.value}),
    FileStatus.FAILED.value: frozenset({FileStatus.DELETED.value}),
    FileStatus.DELETED.value: frozenset(),
}


class FileError(Exception): ...
class InvalidFilePayloadError(FileError): ...
class InvalidFileStatusTransitionError(FileError): ...
class InvalidFileNameError(FileError): ...
class FileTooLargeError(FileError): ...


_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f"\\/]')


def sanitize_filename(raw: str, *, max_length: int = 255) -> str:
    if not isinstance(raw, str):
        raise InvalidFileNameError("filename must be a string")
    s = raw.strip().replace("\\", "/")
    s = s.rsplit("/", 1)[-1]
    s = _UNSAFE_FILENAME_CHARS.sub("", s)
    s = s.replace("..", "_")
    s = s.strip(" .")
    if not s:
        raise InvalidFileNameError("filename must not be empty")
    if len(s) > max_length:
        stem, dot, ext = s.rpartition(".")
        if dot and len(ext) <= 20:
            keep = max_length - len(ext) - 1
            s = f"{stem[:keep]}.{ext}"
        else:
            s = s[:max_length]
    return s


def storage_key_for(
    *, project_id: uuid.UUID, file_id: uuid.UUID
) -> str:
    return f"projects/{project_id}/files/{file_id}/original"


def can_transition_file(current: str, target: str) -> bool:
    if current not in ALL_FILE_STATUSES or target not in ALL_FILE_STATUSES:
        return False
    return target in _ALLOWED_FILE_TRANSITIONS[current]


def is_processing_terminal(status: str) -> bool:
    return status in _PROCESSING_TERMINAL


def is_absolute_terminal(status: str) -> bool:
    return status in _ABSOLUTE_TERMINAL


_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document"
)
_XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet"
)
_PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument"
    ".presentationml.presentation"
)


def detect_mime_from_bytes(head: bytes) -> str | None:
    if not head:
        return None
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"{\\rtf"):
        return "application/rtf"
    if head.startswith(b"PK\x03\x04"):
        window = head[:4096]
        if b"[Content_Types].xml" in window:
            if b"word/" in window:
                return _DOCX_MIME
            if b"xl/" in window:
                return _XLSX_MIME
            if b"ppt/" in window:
                return _PPTX_MIME
        return "application/zip"
    if head.startswith(b"\x1f\x8b"):
        return "application/gzip"
    return None


_MIME_TO_KIND: dict[str, FileKind] = {
    "application/pdf": FileKind.PDF,
    "image/png": FileKind.IMAGE,
    "image/jpeg": FileKind.IMAGE,
    "image/gif": FileKind.IMAGE,
    "image/webp": FileKind.IMAGE,
    "image/svg+xml": FileKind.IMAGE,
    "text/plain": FileKind.TEXT,
    "text/markdown": FileKind.TEXT,
    "text/csv": FileKind.STRUCTURED_DATA,
    "application/json": FileKind.STRUCTURED_DATA,
    "application/xml": FileKind.STRUCTURED_DATA,
    "text/xml": FileKind.STRUCTURED_DATA,
    "text/html": FileKind.DOCUMENT,
    "application/rtf": FileKind.DOCUMENT,
    "application/zip": FileKind.ARCHIVE,
    "application/x-tar": FileKind.ARCHIVE,
    "application/gzip": FileKind.ARCHIVE,
    _DOCX_MIME: FileKind.DOCUMENT,
    _XLSX_MIME: FileKind.SPREADSHEET,
    _PPTX_MIME: FileKind.PRESENTATION,
}

_EXT_TO_KIND: dict[str, FileKind] = {
    ".pdf": FileKind.PDF,
    ".png": FileKind.IMAGE,
    ".jpg": FileKind.IMAGE,
    ".jpeg": FileKind.IMAGE,
    ".gif": FileKind.IMAGE,
    ".webp": FileKind.IMAGE,
    ".svg": FileKind.IMAGE,
    ".txt": FileKind.TEXT,
    ".md": FileKind.TEXT,
    ".csv": FileKind.STRUCTURED_DATA,
    ".json": FileKind.STRUCTURED_DATA,
    ".xml": FileKind.STRUCTURED_DATA,
    ".yaml": FileKind.STRUCTURED_DATA,
    ".yml": FileKind.STRUCTURED_DATA,
    ".zip": FileKind.ARCHIVE,
    ".tar": FileKind.ARCHIVE,
    ".gz": FileKind.ARCHIVE,
    ".doc": FileKind.DOCUMENT,
    ".docx": FileKind.DOCUMENT,
    ".odt": FileKind.DOCUMENT,
    ".rtf": FileKind.DOCUMENT,
    ".html": FileKind.DOCUMENT,
    ".htm": FileKind.DOCUMENT,
    ".xls": FileKind.SPREADSHEET,
    ".xlsx": FileKind.SPREADSHEET,
    ".ods": FileKind.SPREADSHEET,
    ".ppt": FileKind.PRESENTATION,
    ".pptx": FileKind.PRESENTATION,
    ".odp": FileKind.PRESENTATION,
    ".py": FileKind.CODE,
    ".js": FileKind.CODE,
    ".ts": FileKind.CODE,
    ".go": FileKind.CODE,
    ".rs": FileKind.CODE,
    ".java": FileKind.CODE,
    ".c": FileKind.CODE,
    ".cpp": FileKind.CODE,
    ".h": FileKind.CODE,
    ".hpp": FileKind.CODE,
    ".sh": FileKind.CODE,
    ".sql": FileKind.CODE,
}


def classify(
    *,
    detected_mime: str | None,
    client_mime: str | None,
    extension: str | None,
) -> FileKind:
    """Priority: detected content type > client MIME > extension > unknown."""
    for candidate in (detected_mime, client_mime):
        if candidate:
            base = candidate.split(";", 1)[0].strip().lower()
            if base in _MIME_TO_KIND:
                return _MIME_TO_KIND[base]
            if base.startswith("image/"):
                return FileKind.IMAGE
            if base.startswith("text/"):
                return FileKind.TEXT
    if extension:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        if ext in _EXT_TO_KIND:
            return _EXT_TO_KIND[ext]
    return FileKind.UNKNOWN


def initial_extraction_status(
    kind: FileKind,
    *,
    detected_mime: str | None,
    client_mime: str | None,
) -> ExtractionStatus:
    """Decide the initial extraction_status without wasting a job.

    Must stay in sync with ``services.file_extraction.extract_bytes``:
    if that function cannot extract a kind, this must not return QUEUED.
    """
    if kind in (FileKind.PDF, FileKind.TEXT):
        return ExtractionStatus.QUEUED
    if kind == FileKind.DOCUMENT:
        mime = detected_mime or client_mime
        if mime:
            base = mime.split(";", 1)[0].strip().lower()
            if base in ("text/html", "application/xhtml+xml"):
                return ExtractionStatus.QUEUED
    return ExtractionStatus.NOT_SUPPORTED


def extension_of(filename: str) -> str | None:
    _, dot, ext = filename.rpartition(".")
    if not dot or not ext:
        return None
    if len(ext) > 16:
        return None
    return "." + ext.lower()
