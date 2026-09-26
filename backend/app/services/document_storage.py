"""Document storage abstraction.

Defines a minimal interface for storing/retrieving uploaded originals plus a
local-filesystem implementation for development. A future object-storage
backend (S3, Azure Blob, MinIO, …) only needs to implement DocumentStorage —
callers never touch filesystem paths, only opaque storage keys.

Files are written atomically (temp file + rename) under a generated
collision-resistant key; the client-provided filename is never used on disk.
"""

import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from app.exceptions import NotFoundError, StorageError

logger = logging.getLogger(__name__)

# How many bytes of a stored file to read back for download responses.
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def generate_storage_key(extension: str) -> str:
    """Collision-resistant storage key, e.g. '3f2c...-....pdf'."""
    safe_ext = extension.lower().lstrip(".")
    return f"{uuid.uuid4().hex}.{safe_ext}"


class DocumentStorage(ABC):
    """Storage interface — swap the implementation for cloud object storage later."""

    @abstractmethod
    def save(self, key: str, chunks: Iterable[bytes]) -> int:
        """Persist the given byte chunks under `key`. Returns bytes written."""

    @abstractmethod
    def open(self, key: str) -> Iterable[bytes]:
        """Yield the stored file's content in chunks."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete the stored file. Returns True if it existed."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether the key currently holds a stored file."""


class LocalFileStorage(DocumentStorage):
    """Local-filesystem storage for development.

    Keys are generated UUID filenames; every read is resolved inside the base
    directory to rule out path traversal. Writes are atomic.
    """

    def __init__(self, base_path: str | os.PathLike[str]):
        self._base = Path(base_path).resolve()
        try:
            self._base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Cannot create storage directory: {exc}") from exc

    # -- internal helpers ----------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Resolve a key strictly inside the storage root."""
        if not key or "/" in key or "\\" in key or ".." in key:
            raise StorageError("Invalid storage key.")
        candidate = (self._base / key).resolve()
        if candidate.parent != self._base:
            raise StorageError("Invalid storage key.")
        return candidate

    # -- DocumentStorage API ---------------------------------------------------

    def save(self, key: str, chunks: Iterable[bytes]) -> int:
        target = self._resolve(key)
        written = 0
        temp_path = target.with_name(f".{target.name}.tmp")
        try:
            with temp_path.open("wb") as out:
                for chunk in chunks:
                    out.write(chunk)
                    written += len(chunk)
            os.replace(temp_path, target)  # atomic on same filesystem
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            logger.exception("Failed to store document %s", key)
            raise StorageError("Could not store the uploaded file.") from exc
        return written

    def open(self, key: str) -> Iterable[bytes]:
        target = self._resolve(key)
        if not target.is_file():
            raise NotFoundError("Stored file not found.")
        try:
            with target.open("rb") as src:
                while chunk := src.read(DOWNLOAD_CHUNK_SIZE):
                    yield chunk
        except OSError as exc:
            raise StorageError("Could not read the stored file.") from exc

    def delete(self, key: str) -> bool:
        target = self._resolve(key)
        if not target.exists():
            return False
        try:
            target.unlink()
            return True
        except OSError as exc:
            raise StorageError("Could not delete the stored file.") from exc

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageError:
            return False
