"""Upload security gates: content validation, archive-bomb protection and optional AV."""
from __future__ import annotations

import io
import socket
import tarfile
import zipfile

from app.core.config import get_settings
from app.core.exceptions import AppError


class MaliciousFileError(AppError):
    code = "MALICIOUS_FILE"
    status_code = 422
    message = "The uploaded file failed security scanning."


class ArchiveUnsafeError(AppError):
    code = "UNSAFE_ARCHIVE"
    status_code = 422
    message = "The uploaded archive exceeds safe extraction limits."


class FileScanUnavailable(AppError):
    code = "FILE_SCAN_UNAVAILABLE"
    status_code = 503
    message = "Required malware scanning is unavailable."


def validate_upload_bytes(
    content: bytes,
    *,
    detected_mime: str | None,
    extension: str | None,
) -> None:
    settings = get_settings()
    if not content:
        raise MaliciousFileError("empty uploads are not accepted")

    _validate_magic_consistency(content, detected_mime, extension)

    mime = (detected_mime or "").lower()
    archive_extensions = {".zip", ".tar", ".tgz", ".tar.gz", ".gz", ".docx", ".xlsx", ".pptx"}
    if mime in {
        "application/zip",
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    } or (extension or "").lower() in archive_extensions:
        _validate_archive(
            content,
            settings.file_max_archive_entries,
            settings.file_max_archive_uncompressed_bytes,
            settings.file_max_archive_ratio,
            extension=extension,
        )

    if settings.file_malware_scan_mode != "off":
        _clamav_scan(content)


def _validate_magic_consistency(content: bytes, detected_mime: str | None, extension: str | None) -> None:
    ext = (extension or "").lower()
    mime = (detected_mime or "").lower()

    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise MaliciousFileError("PDF extension does not match content")
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"} and not mime.startswith("image/"):
        raise MaliciousFileError("image extension does not match content")
    if ext in {".zip", ".docx", ".xlsx", ".pptx"} and not content.startswith(b"PK"):
        raise MaliciousFileError("archive extension does not match content")
    if ext == ".html" and mime not in {"text/html", "application/xhtml+xml"}:
        # Do not force a MIME mismatch when the detector could not identify text.
        if mime:
            raise MaliciousFileError("HTML extension does not match content")


def _validate_archive(
    content: bytes,
    max_entries: int,
    max_uncompressed_bytes: int,
    max_ratio: float,
    *,
    extension: str | None,
) -> None:
    if content.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > max_entries:
                    raise ArchiveUnsafeError("archive contains too many entries")
                total = 0
                compressed = 0
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if name.startswith("/") or any(part == ".." for part in name.split("/")):
                        raise ArchiveUnsafeError("archive path traversal detected")
                    if info.is_dir():
                        continue
                    if info.flag_bits & 0x1:
                        raise ArchiveUnsafeError("encrypted archives are not accepted")
                    total += max(0, info.file_size)
                    compressed += max(1, info.compress_size)
                    if total > max_uncompressed_bytes:
                        raise ArchiveUnsafeError("archive uncompressed size exceeds limit")
                if total and total / compressed > max_ratio:
                    raise ArchiveUnsafeError("archive compression ratio exceeds limit")
        except zipfile.BadZipFile as exc:
            raise MaliciousFileError("invalid ZIP/OOXML container") from exc
        return

    if (extension or "").lower() in {".tar", ".tgz", ".tar.gz", ".gz"}:
        try:
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
                _validate_tar_members(archive, max_entries, max_uncompressed_bytes)
        except (tarfile.TarError, OSError) as exc:
            raise MaliciousFileError("invalid TAR archive") from exc
        return

    if content.startswith(b"\x1f\x8b"):
        try:
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
                _validate_tar_members(archive, max_entries, max_uncompressed_bytes)
        except (tarfile.TarError, OSError) as exc:
            raise MaliciousFileError("invalid gzip archive") from exc


def _validate_tar_members(archive: tarfile.TarFile, max_entries: int, max_uncompressed_bytes: int) -> None:
    members = archive.getmembers()
    if len(members) > max_entries:
        raise ArchiveUnsafeError("archive contains too many entries")
    total = 0
    for member in members:
        name = member.name.replace("\\", "/")
        if name.startswith("/") or any(part == ".." for part in name.split("/")):
            raise ArchiveUnsafeError("archive path traversal detected")
        if member.issym() or member.islnk() or member.isdev():
            raise ArchiveUnsafeError("archive links/devices are not accepted")
        total += max(0, int(member.size))
        if total > max_uncompressed_bytes:
            raise ArchiveUnsafeError("archive uncompressed size exceeds limit")


def _clamav_scan(content: bytes) -> None:
    settings = get_settings()
    host = settings.file_malware_scan_host
    port = settings.file_malware_scan_port
    try:
        with socket.create_connection((host, port), timeout=settings.file_malware_scan_timeout_seconds) as sock:
            sock.sendall(b"zINSTREAM\0")
            view = memoryview(content)
            for start in range(0, len(content), 1024 * 1024):
                chunk = view[start:start + 1024 * 1024]
                sock.sendall(len(chunk).to_bytes(4, "big"))
                sock.sendall(chunk)
            sock.sendall((0).to_bytes(4, "big"))
            result = sock.recv(4096).decode("utf-8", "replace").strip().lower()
    except OSError as exc:
        if settings.file_malware_scan_mode == "required":
            raise FileScanUnavailable() from exc
        return

    if "found" in result or "virus" in result:
        raise MaliciousFileError("malware detected")
    if not result.endswith("ok") and settings.file_malware_scan_mode == "required":
        raise FileScanUnavailable()


__all__ = [
    "ArchiveUnsafeError", "FileScanUnavailable", "MaliciousFileError",
    "validate_upload_bytes",
]
