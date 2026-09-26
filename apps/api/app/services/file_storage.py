"""M19/M39 storage abstraction with local and S3 implementations."""
from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import REPO_ROOT, get_settings
from app.core.exceptions import StorageUnavailable


class StorageProvider(ABC):
    @abstractmethod
    def put_stream(
        self,
        *,
        key: str,
        chunks: Iterator[bytes],
    ) -> int:
        ...

    @abstractmethod
    def open(self, *, key: str) -> Iterator[bytes]:
        ...

    @abstractmethod
    def delete(self, *, key: str) -> bool:
        ...

    @abstractmethod
    def exists(self, *, key: str) -> bool:
        ...

    @abstractmethod
    def get_size(self, *, key: str) -> int:
        ...

    def presign_get(
        self,
        *,
        key: str,
        expires_seconds: int = 300,
    ) -> str | None:
        return None


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("Invalid storage key.")
        path = (self._root / key).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise StorageUnavailable(
                "Storage key escapes configured root."
            ) from exc
        return path

    def put_stream(
        self,
        *,
        key: str,
        chunks: Iterator[bytes],
    ) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".part")
        total = 0
        try:
            with temp.open("wb") as handle:
                for chunk in chunks:
                    if chunk:
                        handle.write(chunk)
                        total += len(chunk)
            os.replace(temp, path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
        return total

    def open(self, *, key: str) -> Iterator[bytes]:
        path = self._path(key)
        if not path.is_file():
            raise StorageUnavailable("Stored object was not found.")

        def _iterator() -> Iterator[bytes]:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return _iterator()

    def delete(self, *, key: str) -> bool:
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise StorageUnavailable(
                "Stored object could not be deleted."
            ) from exc
        return True

    def exists(self, *, key: str) -> bool:
        return self._path(key).is_file()

    def get_size(self, *, key: str) -> int:
        try:
            return self._path(key).stat().st_size
        except FileNotFoundError as exc:
            raise StorageUnavailable(
                "Stored object was not found."
            ) from exc


class S3StorageProvider(StorageProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.storage_s3_bucket:
            raise StorageUnavailable(
                "S3 bucket is not configured."
            )

        self._bucket = settings.storage_s3_bucket
        self._prefix = settings.storage_s3_prefix.strip("/")
        self._client = boto3.client(
            "s3",
            region_name=settings.storage_s3_region or None,
            endpoint_url=settings.storage_s3_endpoint_url or None,
            aws_access_key_id=(
                settings.storage_s3_access_key_id or None
            ),
            aws_secret_access_key=(
                settings.storage_s3_secret_access_key or None
            ),
        )

    def _key(self, key: str) -> str:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("Invalid storage key.")
        if self._prefix:
            return f"{self._prefix}/{key}"
        return key

    def put_stream(
        self,
        *,
        key: str,
        chunks: Iterator[bytes],
    ) -> int:
        total = 0
        try:
            with tempfile.SpooledTemporaryFile(
                max_size=8 * 1024 * 1024,
                mode="w+b",
            ) as handle:
                for chunk in chunks:
                    if chunk:
                        handle.write(chunk)
                        total += len(chunk)
                handle.seek(0)
                self._client.upload_fileobj(
                    handle,
                    self._bucket,
                    self._key(key),
                )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise StorageUnavailable(
                "Object upload failed."
            ) from exc
        return total

    def open(self, *, key: str) -> Iterator[bytes]:
        try:
            body = self._client.get_object(
                Bucket=self._bucket,
                Key=self._key(key),
            )["Body"]
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable(
                "Stored object was not found."
            ) from exc

        def _iterator() -> Iterator[bytes]:
            try:
                while True:
                    chunk = body.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        return _iterator()

    def delete(self, *, key: str) -> bool:
        try:
            self._client.delete_object(
                Bucket=self._bucket,
                Key=self._key(key),
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable(
                "Stored object could not be deleted."
            ) from exc
        return True

    def exists(self, *, key: str) -> bool:
        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=self._key(key),
            )
        except self._client.exceptions.ClientError as exc:
            code = str(
                exc.response.get("Error", {}).get("Code", "")
            )
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageUnavailable(
                "Object metadata lookup failed."
            ) from exc
        except BotoCoreError as exc:
            raise StorageUnavailable(
                "Object metadata lookup failed."
            ) from exc
        return True

    def get_size(self, *, key: str) -> int:
        try:
            return int(
                self._client.head_object(
                    Bucket=self._bucket,
                    Key=self._key(key),
                )["ContentLength"]
            )
        except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
            raise StorageUnavailable(
                "Object metadata lookup failed."
            ) from exc

    def presign_get(
        self,
        *,
        key: str,
        expires_seconds: int = 300,
    ) -> str | None:
        try:
            return str(
                self._client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": self._key(key),
                    },
                    ExpiresIn=max(
                        1,
                        min(expires_seconds, 3600),
                    ),
                )
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable(
                "Signed URL generation failed."
            ) from exc


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.file_storage_backend == "s3":
        return S3StorageProvider()

    root = Path(settings.file_storage_local_root)
    if not root.is_absolute():
        root = REPO_ROOT / "apps" / "api" / root
    return LocalStorageProvider(root)
