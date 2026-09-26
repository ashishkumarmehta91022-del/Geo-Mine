"""LocalFileStorage tests (no PostgreSQL required, uses a temp directory)."""

import pytest

from app.exceptions import NotFoundError, StorageError
from app.services.document_storage import LocalFileStorage, generate_storage_key


@pytest.fixture()
def storage(tmp_path):
    return LocalFileStorage(tmp_path / "documents")


def test_generate_storage_key_is_uuid_based_and_collision_resistant():
    key1 = generate_storage_key(".pdf")
    key2 = generate_storage_key(".pdf")
    assert key1.endswith(".pdf") and key2.endswith(".pdf")
    assert key1 != key2
    assert "/" not in key1 and ".." not in key1


def test_save_open_roundtrip_streams_content(storage):
    key = generate_storage_key(".pdf")
    written = storage.save(key, iter([b"chunk1-", b"chunk2-"]))
    assert written == len(b"chunk1-chunk2-")
    assert storage.exists(key)
    assert b"".join(storage.open(key)) == b"chunk1-chunk2-"


def test_save_is_atomic_no_temp_files_left(storage):
    key = generate_storage_key(".pdf")
    storage.save(key, iter([b"data"]))
    leftovers = [p.name for p in storage._base.iterdir()]
    assert leftovers == [key]


def test_delete_removes_file_and_reports_missing(storage):
    key = generate_storage_key(".pdf")
    storage.save(key, iter([b"data"]))
    assert storage.delete(key) is True
    assert storage.exists(key) is False
    assert storage.delete(key) is False


def test_open_missing_file_raises_not_found(storage):
    with pytest.raises(NotFoundError):
        list(storage.open("missing.pdf"))


@pytest.mark.parametrize("bad_key", ["../evil.pdf", "sub/dir.pdf", "..\\.\\evil.pdf", ""])
def test_malicious_keys_rejected(storage, bad_key):
    with pytest.raises(StorageError):
        storage.save(bad_key, iter([b"x"]))
    with pytest.raises(StorageError):
        list(storage.open(bad_key))
    assert storage.exists(bad_key) is False
