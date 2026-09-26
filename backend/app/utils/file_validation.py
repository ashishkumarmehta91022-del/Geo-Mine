"""Centralized upload file validation.

Validation is defense-in-depth and deliberately does NOT trust the client:
1. filename sanitization (path traversal, null bytes, absolute paths)
2. extension allowlist (single source of truth for supported categories)
3. declared MIME type policy (weak signal — browsers vary)
4. file-size limit
5. content verification: magic bytes for PDF/PNG/JPEG, ZIP container check
   with required OOXML entries for DOCX/XLSX

No content parsing/extraction happens here (that is a later step).
"""

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.exceptions import FileTooLargeError, InvalidFileError

# ---------------------------------------------------------------------------
# Allowlist — single source of truth for supported document categories.
# ---------------------------------------------------------------------------

# Canonical document_type -> allowed extensions.
ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "pdf": {".pdf"},
    "docx": {".docx"},
    "xlsx": {".xlsx", ".xls"},
    "image": {".png", ".jpg", ".jpeg"},
}

# All extensions accepted by the platform, e.g. {".pdf", ".docx", ...}.
ALL_ALLOWED_EXTENSIONS: frozenset[str] = frozenset().union(*ALLOWED_EXTENSIONS.values())

# Canonical document_type -> client-declared MIME types we accept (weak signal).
ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        # Some producers omit the full OOXML type; content checks below decide.
        "application/octet-stream",
        "application/zip",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
        "application/zip",
    },
    "image": {"image/png", "image/jpeg"},
}

# Every declared MIME type the platform tolerates before content checks.
ALL_ALLOWED_MIME_TYPES: frozenset[str] = frozenset().union(*ALLOWED_MIME_TYPES.values())

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB — streaming copy granularity


@dataclass(frozen=True)
class ValidatedUpload:
    """Result of validating an upload, before storage."""

    original_filename: str  # sanitized, display-only metadata
    extension: str  # lowercase, with dot (e.g. ".pdf")
    document_type: str  # canonical category: pdf | docx | xlsx | image


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(raw_filename: str | None) -> str:
    """Return a safe, human-readable display name.

    Strips any directory components (path traversal, absolute paths),
    removes null bytes and control characters, and enforces a sane length.
    Raises InvalidFileError when nothing usable remains.
    """
    if not raw_filename:
        raise InvalidFileError("No filename provided.")

    # Null bytes never belong in a filename.
    if "\x00" in raw_filename:
        raise InvalidFileError("Filename contains invalid characters.")

    # Keep only the final path component (handles "../", "..\\", "C:\\...", "/etc/...").
    name = posixpath.basename(raw_filename.replace("\\", "/"))
    # Drop a possible remaining drive-letter prefix like "C:".
    name = name.split(":")[-1]
    # Remove control characters and the standard set of forbidden characters.
    cleaned = "".join(
        ch for ch in name if ord(ch) >= 32 and ch not in '<>:"|?*'
    ).strip().strip(".")

    if not cleaned or cleaned in {"..", "."}:
        raise InvalidFileError("Filename is empty after sanitization.")
    if len(cleaned) > 255:
        raise InvalidFileError("Filename is too long.")
    return cleaned


# ---------------------------------------------------------------------------
# Signature / content verification
# ---------------------------------------------------------------------------

def _has_zip_magic(head: bytes) -> bool:
    # ZIP local file header, or the occasional empty-archive marker.
    return head[:4] == b"PK\x03\x04" or head[:4] == b"PK\x05\x06"


def _verify_pdf(head: bytes) -> None:
    if not head.startswith(b"%PDF-"):
        raise InvalidFileError("File content does not look like a valid PDF.")


def _verify_png(head: bytes) -> None:
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise InvalidFileError("File content does not look like a valid PNG image.")


def _verify_jpeg(head: bytes) -> None:
    if head[:3] != b"\xff\xd8\xff":
        raise InvalidFileError("File content does not look like a valid JPEG image.")


def _verify_ooxml_container(head: bytes, required_entry: str) -> None:
    """DOCX/XLSX are ZIP containers; require the magic bytes and their key entry."""
    if not _has_zip_magic(head):
        raise InvalidFileError(
            "File content does not look like a valid Office document (ZIP container expected)."
        )
    # Lightweight scan of header bytes for the required entry name. Reading the
    # full central directory is unnecessary here — the processing pipeline in a
    # later step will parse content properly.
    if required_entry.encode() not in head:
        raise InvalidFileError(
            f"File is a ZIP container but missing the expected Office entry ({required_entry})."
        )


def verify_content(head: bytes, document_type: str, extension: str) -> None:
    """Verify file signature/content for the given category and extension.

    The declared extension decides which signature is required — a ".png"
    file must carry the PNG magic, never the JPEG one. `head` must contain
    at least the first 2 KiB of the file.
    """
    if document_type == "pdf":
        _verify_pdf(head)
    elif document_type == "image":
        if extension == ".png":
            _verify_png(head)
        else:
            _verify_jpeg(head)
    elif document_type == "docx":
        _verify_ooxml_container(head, "word/")
    elif document_type == "xlsx":
        _verify_ooxml_container(head, "xl/")


# ---------------------------------------------------------------------------
# Whole-upload validation pipeline
# ---------------------------------------------------------------------------

def validate_upload(
    *,
    raw_filename: str | None,
    declared_content_type: str | None,
    size_bytes: int | None,
    max_size_bytes: int,
    head: bytes,
) -> ValidatedUpload:
    """Run the full validation pipeline for an upload.

    Args:
        raw_filename: client-provided filename (untrusted).
        declared_content_type: client-provided MIME type (weak signal).
        size_bytes: total size if known up front (None = unknown).
        max_size_bytes: configured limit.
        head: first bytes of the file for signature verification.

    Returns:
        ValidatedUpload with sanitized metadata and the canonical type.

    Raises:
        InvalidFileError: unsupported/unsanitizable/failed content checks.
        FileTooLargeError: size above the configured limit.
    """
    original_filename = sanitize_filename(raw_filename)

    extension = PurePosixPath(original_filename).suffix.lower()
    if not extension or extension not in ALL_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALL_ALLOWED_EXTENSIONS))
        raise InvalidFileError(
            f"Unsupported file type '{extension or '(none)'}'. Allowed: {allowed}."
        )

    document_type = next(
        dtype for dtype, exts in ALLOWED_EXTENSIONS.items() if extension in exts
    )

    if declared_content_type:
        base_type = declared_content_type.split(";")[0].strip().lower()
        if base_type not in ALL_ALLOWED_MIME_TYPES:
            raise InvalidFileError(
                f"Unexpected content type '{base_type}' for a {extension} file."
            )

    if size_bytes is not None and size_bytes > max_size_bytes:
        limit_mb = max_size_bytes // (1024 * 1024)
        raise FileTooLargeError(f"File exceeds the {limit_mb} MB upload limit.")

    verify_content(head, document_type, extension)

    return ValidatedUpload(
        original_filename=original_filename,
        extension=extension,
        document_type=document_type,
    )
