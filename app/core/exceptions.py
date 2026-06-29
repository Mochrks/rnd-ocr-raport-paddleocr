"""
app/core/exceptions.py
=======================
Custom exception classes for the OCR service.

Design rules:
- Each exception maps to exactly one HTTP status code.
- All exceptions carry a human-readable message.
- Global handlers in main.py catch these and return consistent JSON responses.
- No bare `except Exception` or inline `import traceback` in endpoint handlers.
"""

from __future__ import annotations


# ── Domain / Business Exceptions ───────────────────────────────────────────

class UnsupportedFileTypeError(ValueError):
    """
    Raised when an uploaded file has an extension not in the allowed list.
    Maps to HTTP 400 Bad Request.
    """

    def __init__(self, filename: str, allowed: list[str]) -> None:
        ext_list = ", ".join(allowed)
        super().__init__(
            f"Unsupported file type: '{filename}'. "
            f"Allowed extensions: {ext_list}"
        )


class FileTooLargeError(ValueError):
    """
    Raised when an uploaded file exceeds the configured size limit.
    Maps to HTTP 413 Request Entity Too Large.
    """

    def __init__(self, size_mb: float, max_mb: int) -> None:
        super().__init__(
            f"File size {size_mb:.1f} MB exceeds the maximum allowed {max_mb} MB."
        )


class DocumentNotFoundError(KeyError):
    """
    Raised when a document ID does not exist in the document store.
    Maps to HTTP 404 Not Found.
    """

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(f"Document not found: '{document_id}'")


class ImageReadError(IOError):
    """
    Raised when OpenCV cannot read an image file.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, image_path: str) -> None:
        super().__init__(f"Could not read image: '{image_path}'")


class OCRProcessingError(RuntimeError):
    """
    Raised when the OCR pipeline fails unexpectedly.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, detail: str, document_id: str = "") -> None:
        self.document_id = document_id
        prefix = f"[{document_id}] " if document_id else ""
        super().__init__(f"{prefix}OCR processing failed: {detail}")


class PDFConversionError(RuntimeError):
    """
    Raised when PDF-to-image conversion fails and no fallback is available.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, pdf_path: str, reason: str) -> None:
        super().__init__(
            f"Could not convert PDF '{pdf_path}' to images: {reason}"
        )
