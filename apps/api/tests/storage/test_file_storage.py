"""M19 — LocalStorageProvider tests."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.exceptions import StorageUnavailable
from app.services.file_storage import LocalStorageProvider


@pytest.fixture()
def provider(tmp_path) -> LocalStorageProvider:
    return LocalStorageProvider(tmp_path)


def _chunks(data: bytes, size: int = 8) -> Iterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


def test_put_and_read(provider):
    n = provider.put_stream(key="a/b/c.bin", chunks=_chunks(b"hello world"))
    assert n == 11
    assert provider.exists(key="a/b/c.bin")
    assert provider.get_size(key="a/b/c.bin") == 11
    assert b"".join(provider.open(key="a/b/c.bin")) == b"hello world"


def test_delete(provider):
    provider.put_stream(key="x.bin", chunks=_chunks(b"z"))
    assert provider.delete(key="x.bin") is True
    assert provider.delete(key="x.bin") is False
    assert not provider.exists(key="x.bin")


def test_open_missing(provider):
    with pytest.raises(StorageUnavailable):
        provider.open(key="missing.bin")


def test_get_size_missing(provider):
    with pytest.raises(StorageUnavailable):
        provider.get_size(key="missing.bin")


@pytest.mark.parametrize(
    "bad_key", ["", "/abs/path", "../escape", "a/../b", ".."]
)
def test_rejects_path_traversal(provider, bad_key):
    with pytest.raises(StorageUnavailable):
        provider.put_stream(key=bad_key, chunks=_chunks(b"x"))


def test_partial_write_cleanup(provider, tmp_path):
    def exploding() -> Iterator[bytes]:
        yield b"partial"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        provider.put_stream(key="will/fail.bin", chunks=exploding())
    assert list(tmp_path.rglob("*.part")) == []
    assert not provider.exists(key="will/fail.bin")


def test_deterministic_key():
    import uuid

    from app.domain.file import storage_key_for

    pid = uuid.uuid4()
    fid = uuid.uuid4()
    k1 = storage_key_for(project_id=pid, file_id=fid)
    k2 = storage_key_for(project_id=pid, file_id=fid)
    assert k1 == k2
    assert ".." not in k1
