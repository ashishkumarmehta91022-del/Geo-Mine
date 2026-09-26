"""Document service: upload pipeline, listing, detail, deletion.

Business logic lives here so routes stay thin. The storage backend is
injected (local filesystem today, object storage later).
"""

import logging
from collections.abc import Iterable
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppError, DatabaseUnavailableError, InvalidFileError
from app.models import Document
from app.services.document_storage import DocumentStorage, generate_storage_key
from app.utils.file_validation import DEFAULT_CHUNK_SIZE, validate_upload

logger = logging.getLogger(__name__)


def _stream_limited(source: BinaryIO, first_chunk: bytes, max_bytes: int) -> Iterable[bytes]:
    """Yield upload content in chunks, refusing to buffer more than max_bytes.

    Streams instead of loading the whole file into memory; the size limit is
    enforced while streaming so oversized uploads are cut off early.
    """
    written = len(first_chunk)
    if written > max_bytes:
        raise AppError(
            status_code=413,
            code="file_too_large",
            message="The uploaded file exceeds the allowed size.",
        )
    yield first_chunk
    while chunk := source.read(DEFAULT_CHUNK_SIZE):
        written += len(chunk)
        if written > max_bytes:
            raise AppError(
                status_code=413,
                code="file_too_large",
                message="The uploaded file exceeds the allowed size.",
            )
        yield chunk


def upload_document(
    db: Session, upload: UploadFile, storage: DocumentStorage
) -> Document:
    """Validate, store, and register an uploaded document.

    Raises InvalidFileError / FileTooLargeError from validation; on database
    failure the already-stored file is removed so no orphan is left behind.
    """
    # 1) Read a small head for signature checks (never the whole file).
    head = upload.file.read(2048)
    size_hint = upload.size  # may be None depending on the multipart parser

    # 2) Validate name/extension/declared MIME/signature/limit.
    validated = validate_upload(
        raw_filename=upload.filename,
        declared_content_type=upload.content_type,
        size_bytes=size_hint,
        max_size_bytes=settings.max_upload_size_bytes,
        head=head,
    )

    # 3) Stream to storage under a generated collision-resistant key.
    key = generate_storage_key(validated.extension)
    chunks = _stream_limited(upload.file, head, settings.max_upload_size_bytes)
    storage.save(key, chunks)

    # 4) Register in the database; clean up the stored file on failure.
    document = Document(
        filename=validated.original_filename,
        document_type=validated.document_type,
        source="upload",
        storage_reference=key,
        status="uploaded",
    )
    try:
        db.add(document)
        db.commit()
    except OperationalError as exc:
        db.rollback()
        storage.delete(key)
        logger.warning("Database unavailable during document registration: %s", exc.__class__.__name__)
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        storage.delete(key)
        logger.exception("Document registration failed; stored file %s removed", key)
        raise AppError(
            status_code=500,
            code="document_registration_failed",
            message="The file was stored but could not be registered. Please retry.",
        ) from exc

    return document


def list_documents(db: Session, page: int, page_size: int) -> tuple[list[Document], int]:
    """Return one page of documents (newest first) plus the total count."""
    try:
        total = db.execute(select(func.count()).select_from(Document)).scalar_one()
        rows = db.execute(
            select(Document)
            .order_by(Document.uploaded_at.desc(), Document.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not query documents."
        ) from exc
    return list(rows), int(total)


def get_document(db: Session, document_id: int) -> Document:
    """Fetch one document or raise NotFoundError."""
    try:
        document = db.get(Document, document_id)
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not fetch the document."
        ) from exc
    if document is None:
        raise AppError(status_code=404, code="document_not_found", message="Document not found.")
    return document


def delete_document(db: Session, document: Document, storage: DocumentStorage) -> None:
    """Delete the database record, then the stored file.

    DB-first ordering means a failed file deletion can only leave a harmless
    orphan file (logged), never a record pointing at nothing.
    """
    try:
        db.delete(document)
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise AppError(
            status_code=500, code="database_error", message="Could not delete the document."
        ) from exc

    try:
        storage.delete(document.storage_reference)
    except Exception:  # noqa: BLE001 — record is gone; log the orphan-file risk
        logger.exception(
            "Stored file %s could not be deleted (orphan file possible)",
            document.storage_reference,
        )
