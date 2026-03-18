"""
Normalization Orchestrator.

Single entry point for all document normalization.

Responsibilities:
  1. Detect file type from the file extension (not MIME type — the extension
     is more reliable for VDR-sourced files and is already validated upstream
     at upload time).
  2. Route to the correct normalizer.
  3. Catch and classify normalizer errors:
       NormalizationError       — unrecoverable, do not retry
       UnsupportedFileTypeError — caller should mark document as skipped
  4. Return a NormalizedDocument.

Supported extensions:
  .pdf   → PDF normalizer
  .docx  → DOCX normalizer
  .xlsx  → XLSX normalizer
  .pptx  → PPTX normalizer

Unsupported extensions raise UnsupportedFileTypeError immediately.
The caller (ingestion worker) catches this and marks the document
status as 'failed' with an appropriate error message.

The orchestrator does NOT write to any database or object store.
It is a pure function: bytes + metadata in, NormalizedDocument out.
All persistence is the caller's responsibility.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from packages.core.schemas.document import NormalizedDocument

logger = logging.getLogger(__name__)

# Supported extensions mapped to normalizer function names
_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".pptx"})


class UnsupportedFileTypeError(Exception):
    """
    Raised when the file extension is not supported.

    Attributes:
        extension: The unsupported extension (e.g. '.csv').
        filename:  The original filename for error reporting.
    """
    def __init__(self, extension: str, filename: str) -> None:
        self.extension = extension
        self.filename = filename
        super().__init__(
            f"Unsupported file type '{extension}' for file '{filename}'. "
            f"Supported types: {sorted(_SUPPORTED_EXTENSIONS)}"
        )


class NormalizationError(Exception):
    """
    Raised when a normalizer encounters an unrecoverable error.

    Attributes:
        filename:   The filename that failed.
        extension:  The file extension.
        cause:      The original exception.
    """
    def __init__(self, filename: str, extension: str, cause: Exception) -> None:
        self.filename = filename
        self.extension = extension
        self.cause = cause
        super().__init__(
            f"Normalization failed for '{filename}' ({extension}): "
            f"{type(cause).__name__}: {cause}"
        )


def normalize(
    content: bytes,
    document_id: UUID,
    engagement_id: UUID,
    filename: str,
    vdr_folder_path: Optional[str] = None,
) -> NormalizedDocument:
    """
    Normalize a document file to a NormalizedDocument.

    This is the single entry point for all document normalization.
    Routes to the correct normalizer based on the file extension.

    Args:
        content:          Raw file bytes.
        document_id:      UUID of the document record.
        engagement_id:    UUID of the engagement.
        filename:         Original filename including extension.
        vdr_folder_path:  Optional VDR folder path for metadata.

    Returns:
        NormalizedDocument with all extracted TextBlocks and ExtractedTables.

    Raises:
        UnsupportedFileTypeError: If the file extension is not supported.
        NormalizationError:       If the normalizer raises an unexpected error.
    """
    extension = _extract_extension(filename)

    if extension not in _SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(extension, filename)

    logger.info(
        "Normalizing document_id=%s filename=%s extension=%s bytes=%d",
        document_id,
        filename,
        extension,
        len(content),
    )

    try:
        result = _dispatch(extension, content, document_id, engagement_id,
                           filename, vdr_folder_path)
    except (UnsupportedFileTypeError, NormalizationError):
        raise
    except Exception as exc:
        logger.exception(
            "Normalizer raised unexpected error for %s (%s)", filename, extension
        )
        raise NormalizationError(filename, extension, exc) from exc

    logger.info(
        "Normalization complete: document_id=%s text_blocks=%d tables=%d",
        document_id,
        len(result.text_blocks),
        len(result.tables),
    )

    return result


def supported_extensions() -> frozenset[str]:
    """Return the set of supported file extensions."""
    return _SUPPORTED_EXTENSIONS


def is_supported(filename: str) -> bool:
    """Return True if the file extension is supported."""
    return _extract_extension(filename) in _SUPPORTED_EXTENSIONS


# ─── Private helpers ──────────────────────────────────────────────────────────

def _extract_extension(filename: str) -> str:
    """
    Extract the lowercase file extension from a filename.

    Examples:
        'CIM_Draft.PDF'  → '.pdf'
        'model.xlsx'     → '.xlsx'
        'nodot'          → ''
        ''               → ''
        '.'              → ''   (dot-only has no meaningful extension)
    """
    if "." not in filename:
        return ""
    stem, ext = filename.rsplit(".", 1)
    if not ext:
        return ""   # filename ends with a dot — no extension after it
    return "." + ext.lower()


def _dispatch(
    extension: str,
    content: bytes,
    document_id: UUID,
    engagement_id: UUID,
    filename: str,
    vdr_folder_path: Optional[str],
) -> NormalizedDocument:
    """
    Dispatch to the correct normalizer for the given extension.

    Imports are deferred to inside each branch so that a missing
    optional dependency (e.g. pdfplumber not installed) only raises
    at call time for that format, not at module import time.
    """
    if extension == ".pdf":
        from packages.ingestion.normalizers.pdf import normalize_pdf
        return normalize_pdf(content, document_id, engagement_id,
                             filename, vdr_folder_path)

    if extension == ".docx":
        from packages.ingestion.normalizers.docx import normalize_docx
        return normalize_docx(content, document_id, engagement_id,
                              filename, vdr_folder_path)

    if extension == ".xlsx":
        from packages.ingestion.normalizers.xlsx import normalize_xlsx
        return normalize_xlsx(content, document_id, engagement_id,
                              filename, vdr_folder_path)

    if extension == ".pptx":
        from packages.ingestion.normalizers.pptx import normalize_pptx
        return normalize_pptx(content, document_id, engagement_id,
                              filename, vdr_folder_path)

    # Should never reach here — caller checks _SUPPORTED_EXTENSIONS first
    raise UnsupportedFileTypeError(extension, filename)
