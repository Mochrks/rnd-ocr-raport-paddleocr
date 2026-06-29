"""
app/infrastructure/storage/document_store.py
=============================================
In-memory document store for OCR processing state.

Design:
- Simple dict-backed store suitable for R&D / single-process deployment.
- Encapsulated in a class to make the interface explicit and testable.
- Thread-safe reads for the current single-worker uvicorn setup.
- All mutations go through typed methods — no raw dict access from outside.

If the application grows to need persistence or multi-worker support,
only this module needs to change (swap with Redis, database, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class DocumentRecord:
    """Represents a single uploaded document and its OCR processing state."""

    __slots__ = (
        "id",
        "status",
        "image_path",
        "accuracy",
        "processing_time",
        "extracted_data",
        "personality",
        "attendance",
        "error",
    )

    def __init__(self, document_id: str, image_path: str) -> None:
        self.id: str = document_id
        self.status: str = "PROCESSING"
        self.image_path: str = image_path
        self.accuracy: float = 0.0
        self.processing_time: float = 0.0
        self.extracted_data: list = []
        self.personality: Optional[Dict] = None
        self.attendance: Optional[Dict] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for logging or legacy access."""
        return {
            "id": self.id,
            "status": self.status,
            "image_path": self.image_path,
            "accuracy": self.accuracy,
            "processingTime": self.processing_time,
            "extracted_data": self.extracted_data,
            "personality": self.personality,
            "attendance": self.attendance,
            "error": self.error,
        }


class DocumentStore:
    """
    Thread-safe in-memory store for DocumentRecord objects.

    Usage:
        store = DocumentStore()                  # or use the module singleton
        record = store.create("DOC1A2B3", path)
        store.mark_success("DOC1A2B3", subjects, personality, attendance, 1.23)
        record = store.get("DOC1A2B3")
    """

    def __init__(self) -> None:
        self._store: Dict[str, DocumentRecord] = {}

    def create(self, document_id: str, image_path: str) -> DocumentRecord:
        """Create and register a new document record."""
        record = DocumentRecord(document_id, image_path)
        self._store[document_id] = record
        return record

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        """Return the record for document_id, or None if not found."""
        return self._store.get(document_id)

    def contains(self, document_id: str) -> bool:
        """Return True if the document_id exists in the store."""
        return document_id in self._store

    def mark_success(
        self,
        document_id: str,
        extracted_data: list,
        personality: Optional[Dict],
        attendance: Optional[Dict],
        processing_time: float,
    ) -> None:
        """Update the record after a successful OCR run."""
        record = self._store.get(document_id)
        if record is None:
            return
        record.status = "SUCCESS"
        record.extracted_data = extracted_data
        record.personality = personality
        record.attendance = attendance
        record.processing_time = processing_time

        valid_acc = [
            d["accuracy"]
            for d in extracted_data
            if d.get("accuracy") is not None
        ]
        record.accuracy = round(sum(valid_acc) / len(valid_acc), 1) if valid_acc else 0.0

    def mark_failed(
        self,
        document_id: str,
        error: str,
        processing_time: float,
    ) -> None:
        """Update the record after a failed OCR run."""
        record = self._store.get(document_id)
        if record is None:
            return
        record.status = "FAILED"
        record.error = error
        record.processing_time = processing_time


# Module-level singleton — import this in the application layer
document_store = DocumentStore()
