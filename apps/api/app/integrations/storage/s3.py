"""S3-compatible private object storage adapter."""
from __future__ import annotations

from collections.abc import Iterator
from io import RawIOBase
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.exceptions import StorageUnavailable
from app.services.file_storage import StorageProvider


class _IteratorReader(RawIOBase):
    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._iterator = iter(chunks)
        self._buffer = b""
        self._done = False

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self._done:
            return b""
        if size is None or size < 0:
            data = self._buffer + b"".join(self._iterator)
            self._buffer = b""
            self._done = True
            return data
        while len(self._buffer) < size:
            try:
                self._buffer += next(self._iterator)
            except StopIteration:
                self._done = True
                break
        result = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return result


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None,
        prefix: str,
        signed_url_expire_seconds: int,
    ) -> None:
        if not bucket.strip() or not access_key_id.strip() or not secret_access_key:
            raise StorageUnavailable("S3 storage is not configured")
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._signed_expiry = signed_url_expire_seconds
        try:
            self._client = boto3.client(
                "s3",
                region_name=region or None,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                endpoint_url=endpoint_url or None,
            )
        except Exception as exc:
            raise StorageUnavailable("failed to initialize S3 client") from exc

    def _key(self, key: str) -> str:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise StorageUnavailable("invalid storage key")
        return f"{self._prefix}/{key}" if self._prefix else key

    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        object_key = self._key(key)
        reader = _IteratorReader(chunks)
        try:
            self._client.upload_fileobj(
                reader,
                self._bucket,
                object_key,
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )
            head = self._client.head_object(
                Bucket=self._bucket,
                Key=object_key,
            )
            return int(head.get("ContentLength", 0))
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("S3 upload failed") from exc

    def open(self, *, key: str) -> Iterator[bytes]:
        object_key = self._key(key)
        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("S3 object not found") from exc
        body = response["Body"]

        def _iter() -> Iterator[bytes]:
            try:
                while True:
                    chunk = body.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        return _iter()

    def delete(self, *, key: str) -> bool:
        object_key = self._key(key)
        try:
            self._client.delete_object(
                Bucket=self._bucket,
                Key=object_key,
            )
            return True
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("S3 delete failed") from exc

    def exists(self, *, key: str) -> bool:
        object_key = self._key(key)
        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=object_key,
            )
            return True
        except ClientError:
            return False
        except BotoCoreError as exc:
            raise StorageUnavailable("S3 availability check failed") from exc

    def get_size(self, *, key: str) -> int:
        object_key = self._key(key)
        try:
            response = self._client.head_object(
                Bucket=self._bucket,
                Key=object_key,
            )
            return int(response.get("ContentLength", 0))
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("S3 head failed") from exc

    def signed_download_url(self, *, key: str) -> str:
        object_key = self._key(key)
        try:
            return str(
                self._client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": object_key,
                    },
                    ExpiresIn=self._signed_expiry,
                )
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable("S3 signed URL generation failed") from exc
