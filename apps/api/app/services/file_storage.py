"""M19 — Storage provider abstraction + LocalStorageProvider."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from app.core.exceptions import StorageUnavailable


class StorageProvider(ABC):
    @abstractmethod
    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        """Write ``chunks`` to ``key``. Returns total bytes written."""

    @abstractmethod
    def open(self, *, key: str) -> Iterator[bytes]:
        """Yield file content in chunks."""

    @abstractmethod
    def delete(self, *, key: str) -> bool:
        """Delete object. Returns True if existed and was removed."""

    @abstractmethod
    def exists(self, *, key: str) -> bool: ...

    @abstractmethod
    def get_size(self, *, key: str) -> int: ...


class LocalStorageProvider(StorageProvider):
    """Filesystem-backed storage under a single configured root.

    Safety: every key is validated to stay inside the root.
    User-controlled filenames never become path components — callers
    must pass keys produced by ``domain.file.storage_key_for``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _abs(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("invalid storage key")
        abs_path = (self._root / key).resolve()
        try:
            abs_path.relative_to(self._root)
        except ValueError as exc:
            raise StorageUnavailable("storage key escapes root") from exc
        return abs_path

    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        total = 0
        try:
            with tmp.open("wb") as fh:
                for chunk in chunks:
                    if not chunk:
                        continue
                    fh.write(chunk)
                    total += len(chunk)
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return total

    def open(self, *, key: str) -> Iterator[bytes]:
        path = self._abs(key)
        if not path.is_file():
            raise StorageUnavailable("object not found")

        def _iter() -> Iterator[bytes]:
            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return _iter()

    def delete(self, *, key: str) -> bool:
        path = self._abs(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise StorageUnavailable(str(exc)) from exc
        return True

    def exists(self, *, key: str) -> bool:
        return self._abs(key).is_file()

    def get_size(self, *, key: str) -> int:
        try:
            return self._abs(key).stat().st_size
        except FileNotFoundError as exc:
            raise StorageUnavailable("object not found") from exc


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.file_storage_backend == "s3":
        from app.integrations.storage.s3 import S3StorageProvider

        return S3StorageProvider(
            bucket=settings.file_storage_s3_bucket,
            region=settings.file_storage_s3_region,
            access_key_id=settings.file_storage_s3_access_key_id,
            secret_access_key=settings.file_storage_s3_secret_access_key,
            endpoint_url=settings.file_storage_s3_endpoint_url or None,
            prefix=settings.file_storage_s3_prefix,
            signed_url_expire_seconds=settings.file_storage_s3_signed_url_expire_seconds,
        )
    root = Path(settings.file_storage_local_root)
    if not root.is_absolute():
        root = REPO_ROOT / "apps" / "api" / root
    return LocalStorageProvider(root)
