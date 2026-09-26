"""Document routes: upload, list, detail, download, delete.

Routes stay thin — validation/storage/DB logic lives in the service layer.
Note: no authentication yet (a later step), so deletion is currently
unrestricted by design.
"""

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.exceptions import AppError
from app.models import Document
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.services.document_service import (
    delete_document,
    get_document,
    list_documents,
    upload_document,
)
from app.services.document_storage import LocalFileStorage
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Development storage backend (swap for object storage in a later step).
_storage = LocalFileStorage(settings.document_storage_path)

# Pagination guards.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        document_type=document.document_type,
        source=document.source,
        status=document.status,
        storage_reference=document.storage_reference,
        uploaded_at=document.uploaded_at,
        error_message=document.error_message,
    )


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document_route(upload: UploadFile, db: Session = Depends(get_db)) -> DocumentResponse:
    """Upload a document (multipart/form-data field: `upload`)."""
    document = upload_document(db, upload, _storage)
    return _to_response(document)


@router.get("", response_model=DocumentListResponse)
def list_documents_route(
    page: int = 1, page_size: int = DEFAULT_PAGE_SIZE, db: Session = Depends(get_db)
) -> DocumentListResponse:
    """Paginated document list (newest first)."""
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    documents, total = list_documents(db, page, page_size)
    return DocumentListResponse(
        items=[_to_response(d) for d in documents],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_route(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    """Document metadata (never the file content)."""
    return _to_response(get_document(db, document_id))


@router.get("/{document_id}/download")
def download_document_route(document_id: int, db: Session = Depends(get_db)):
    """Stream the stored original with its original filename."""
    document = get_document(db, document_id)
    extension = document.storage_reference.rsplit(".", 1)[-1].lower()
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    media_type = media_types.get(extension, "application/octet-stream")

    return StreamingResponse(
        _storage.open(document.storage_reference),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"'
        },
    )


@router.delete("/{document_id}", status_code=204)
def delete_document_route(document_id: int, db: Session = Depends(get_db)) -> None:
    """Delete the record and its stored file (unrestricted until auth arrives)."""
    document = get_document(db, document_id)
    delete_document(db, document, _storage)
