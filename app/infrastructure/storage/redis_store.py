import json
from typing import Dict, Optional

import redis

from app.core.config import settings
from app.infrastructure.storage.base import BaseDocumentStore, DocumentRecord


class RedisDocumentStore(BaseDocumentStore):
    """
    Redis-backed document store for multi-worker deployment.
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_client = redis.Redis.from_url(
            redis_url, decode_responses=True, protocol=2
        )
        self.prefix = "ocr_doc:"

    def _get_key(self, document_id: str) -> str:
        return f"{self.prefix}{document_id}"

    def create(self, document_id: str, image_path: str) -> DocumentRecord:
        record = DocumentRecord(document_id, image_path)
        self.redis_client.set(self._get_key(document_id), record.to_json())
        return record

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        data_str = self.redis_client.get(self._get_key(document_id))
        if data_str is None:
            return None
        return DocumentRecord.from_json(data_str)

    def contains(self, document_id: str) -> bool:
        return bool(self.redis_client.exists(self._get_key(document_id)))

    def mark_success(
        self,
        document_id: str,
        extracted_data: list,
        personality: Optional[Dict],
        attendance: Optional[Dict],
        processing_time: float,
    ) -> None:
        record = self.get(document_id)
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

        self.redis_client.set(self._get_key(document_id), record.to_json())

    def mark_failed(
        self,
        document_id: str,
        error: str,
        processing_time: float,
    ) -> None:
        record = self.get(document_id)
        if record is None:
            return

        record.status = "FAILED"
        record.error = error
        record.processing_time = processing_time

        self.redis_client.set(self._get_key(document_id), record.to_json())
