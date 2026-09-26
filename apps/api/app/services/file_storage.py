"""M19/M39 storage abstraction with local and S3 backends."""
from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import REPO_ROOT, get_settings
from app.core.exceptions import StorageUnavailable


class StorageProvider(ABC):
    @abstractmethod
    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int: ...
    @abstractmethod
    def open(self, *, key: str) -> Iterator[bytes]: ...
    @abstractmethod
    def delete(self, *, key: str) -> bool: ...
    @abstractmethod
    def exists(self, *, key: str) -> bool: ...
    @abstractmethod
    def get_size(self, *, key: str) -> int: ...
    def presign_get(self, *, key: str, expires_seconds: int = 300) -> str | None:
        return None


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _abs(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("invalid storage key")
        path = (self._root / key).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise StorageUnavailable("storage key escapes root") from exc
        return path

    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        total = 0
        try:
            with tmp.open("wb") as fh:
                for chunk in chunks:
                    if chunk:
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
                while chunk := fh.read(64 * 1024):
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


class S3StorageProvider(StorageProvider):
    def __init__(self) -> None:
        s = get_settings()
        if not s.storage_s3_bucket or not s.storage_s3_region:
            raise StorageUnavailable("S3 storage is not configured")
        self._bucket = s.storage_s3_bucket
        self._prefix = s.storage_s3_prefix.strip("/")
        self._client = boto3.client(
            "s3",
            region_name=s.storage_s3_region,
            endpoint_url=s.storage_s3_endpoint_url or None,
            aws_access_key_id=s.storage_s3_access_key_id or None,
            aws_secret_access_key=s.storage_s3_secret_access_key or None,
        )

    def _key(self, key: str) -> str:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("invalid storage key")
        return f"{self._prefix}/{key}" if self._prefix else key

    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        total = 0
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as fh:
            try:
                for chunk in chunks:
                    if chunk:
                        fh.write(chunk)
                        total += len(chunk)
                fh.seek(0)
                self._client.upload_fileobj(fh, self._bucket, self._key(key))
            except (BotoCoreError, ClientError, OSError) as exc:
                raise StorageUnavailable("object upload failed") from exc
        return total

    def open(self, *, key: str) -> Iterator[bytes]:
        try:
            body = self._client.get_object(Bucket=self._bucket, Key=self._key(key))["Body"]
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("object not found") from exc
        def _iter() -> Iterator[bytes]:
            try:
                while chunk := body.read(64 * 1024):
                    yield chunk
            finally:
                body.close()
        return _iter()

    def delete(self, *, key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._key(key))
            return True
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("object delete failed") from exc

    def exists(self, *, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(key))
            return True
        except self._client.exceptions.ClientError as exc:
            if getattr(exc.response.get("Error", {}), "get", lambda *_: None)("Code") in ("404", "NoSuchKey"):
                return False
            raise StorageUnavailable("object metadata failed") from exc
        except BotoCoreError as exc:
            raise StorageUnavailable("object metadata failed") from exc

    def get_size(self, *, key: str) -> int:
        try:
            return int(self._client.head_object(Bucket=self._bucket, Key=self._key(key))["ContentLength"])
        except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
            raise StorageUnavailable("object metadata failed") from exc

    def presign_get(self, *, key: str, expires_seconds: int = 300) -> str | None:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": self._key(key)},
                ExpiresIn=max(1, min(expires_seconds, 3600)),
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("signed URL generation failed") from exc


def get_storage_provider() -> StorageProvider:
    s = get_settings()
    backend = s.file_storage_backend
    if backend == "s3":
        return S3StorageProvider()
    root = Path(s.file_storage_local_root)
    if not root.is_absolute():
        root = REPO_ROOT / "apps" / "api" / root
    return LocalStorageProvider(root)
