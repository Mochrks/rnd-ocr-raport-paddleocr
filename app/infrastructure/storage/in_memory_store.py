"""
app/infrastructure/storage/in_memory_store.py
=============================================
In-memory document store for OCR processing state.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.infrastructure.storage.base import BaseDocumentStore, DocumentRecord


class InMemoryDocumentStore(BaseDocumentStore):
    """
    Thread-safe in-memory store for DocumentRecord objects.
    Suitable for single-worker or fallback deployment.
    """

    def __init__(self) -> None:
        self._store: Dict[str, DocumentRecord] = {}

    def create(self, document_id: str, image_path: str) -> DocumentRecord:
        record = DocumentRecord(document_id, image_path)
        self._store[document_id] = record
        return record

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        return self._store.get(document_id)

    def contains(self, document_id: str) -> bool:
        return document_id in self._store

    def mark_success(
        self,
        document_id: str,
        extracted_data: list,
        personality: Optional[Dict],
        attendance: Optional[Dict],
        processing_time: float,
    ) -> None:
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
            if isinstance(d, dict) and d.get("accuracy") is not None
        ]
        record.accuracy = round(sum(valid_acc) / len(valid_acc), 1) if valid_acc else 0.0

    def mark_failed(
        self,
        document_id: str,
        error: str,
        processing_time: float,
    ) -> None:
        record = self._store.get(document_id)
        if record is None:
            return
        record.status = "FAILED"
        record.error = error
        record.processing_time = processing_time
