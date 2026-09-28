"""S3-compatible object storage provider.

Works with AWS S3 and Cloudflare R2. The implementation keeps the
storage abstraction provider-neutral so file routes do not change.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import PurePosixPath

from app.core.config import get_settings
from app.core.exceptions import StorageUnavailable
from app.services.file_storage import StorageProvider


class S3StorageProvider(StorageProvider):
    """Private S3-compatible object storage.

    Uploads use multipart transfer for objects above the in-memory part
    threshold. Reads are streamed directly from the SDK response body.
    """

    _PART_SIZE = 8 * 1024 * 1024

    def __init__(
        self,
        *,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str = "auto",
        path_style: bool = True,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover
            raise StorageUnavailable(
                "S3 storage requires boto3"
            ) from exc

        if not endpoint or not access_key_id or not secret_access_key or not bucket:
            raise StorageUnavailable(
                "S3 storage is not fully configured"
            )

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint.rstrip("/"),
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": (
                        "path" if path_style else "auto"
                    )
                },
            ),
        )

    @staticmethod
    def _validate_key(key: str) -> str:
        if (
            not key
            or key.startswith("/")
            or any(part in {"", ".", ".."} for part in key.split("/"))
            or str(PurePosixPath(key)) != key
        ):
            raise StorageUnavailable("invalid storage key")
        return key

    def put_stream(self, *, key: str, chunks: Iterator[bytes]) -> int:
        key = self._validate_key(key)
        buffered = bytearray()
        total = 0
        multipart_id: str | None = None
        parts: list[dict[str, object]] = []
        part_number = 1

        try:
            for chunk in chunks:
                if not chunk:
                    continue
                buffered.extend(chunk)
                total += len(chunk)

                if multipart_id is None and len(buffered) > self._PART_SIZE:
                    response = self._client.create_multipart_upload(
                        Bucket=self._bucket,
                        Key=key,
                    )
                    multipart_id = response["UploadId"]

                while multipart_id is not None and len(buffered) >= self._PART_SIZE:
                    payload = bytes(buffered[: self._PART_SIZE])
                    del buffered[: self._PART_SIZE]
                    result = self._client.upload_part(
                        Bucket=self._bucket,
                        Key=key,
                        UploadId=multipart_id,
                        PartNumber=part_number,
                        Body=payload,
                    )
                    parts.append(
                        {"PartNumber": part_number, "ETag": result["ETag"]}
                    )
                    part_number += 1

            if multipart_id is None:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=bytes(buffered),
                )
            else:
                if buffered:
                    result = self._client.upload_part(
                        Bucket=self._bucket,
                        Key=key,
                        UploadId=multipart_id,
                        PartNumber=part_number,
                        Body=bytes(buffered),
                    )
                    parts.append(
                        {"PartNumber": part_number, "ETag": result["ETag"]}
                    )
                self._client.complete_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=multipart_id,
                    MultipartUpload={"Parts": parts},
                )
            return total
        except Exception as exc:
            if multipart_id is not None:
                with contextlib.suppress(Exception):
                    self._client.abort_multipart_upload(
                        Bucket=self._bucket,
                        Key=key,
                        UploadId=multipart_id,
                    )
            raise StorageUnavailable(
                f"S3 upload failed: {type(exc).__name__}"
            ) from exc

    def open(self, *, key: str) -> Iterator[bytes]:
        key = self._validate_key(key)
        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            body = response["Body"]
        except Exception as exc:
            raise StorageUnavailable("object not found") from exc

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
        key = self._validate_key(key)
        existed = self.exists(key=key)
        if not existed:
            return False
        try:
            self._client.delete_object(
                Bucket=self._bucket,
                Key=key,
            )
        except Exception as exc:
            raise StorageUnavailable("S3 delete failed") from exc
        return True

    def exists(self, *, key: str) -> bool:
        key = self._validate_key(key)
        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=key,
            )
            return True
        except Exception as exc:
            status = getattr(
                getattr(exc, "response", None),
                "get",
                lambda *_: None,
            )("ResponseMetadata", {})
            code = status.get("HTTPStatusCode") if isinstance(status, dict) else None
            if code == 404:
                return False
            raise StorageUnavailable("S3 head request failed") from exc

    def get_size(self, *, key: str) -> int:
        key = self._validate_key(key)
        try:
            response = self._client.head_object(
                Bucket=self._bucket,
                Key=key,
            )
            return int(response["ContentLength"])
        except Exception as exc:
            raise StorageUnavailable("S3 head request failed") from exc


def build_s3_storage_provider() -> S3StorageProvider:
    settings = get_settings()
    return S3StorageProvider(
        endpoint=settings.storage_endpoint,
        access_key_id=settings.storage_access_key_id,
        secret_access_key=settings.storage_secret_access_key,
        bucket=settings.storage_bucket,
        region=settings.storage_region,
        path_style=settings.storage_path_style,
    )
