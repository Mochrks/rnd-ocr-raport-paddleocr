import json
from abc import ABC, abstractmethod
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

    def __init__(
        self,
        document_id: str,
        image_path: str,
        status: str = "PROCESSING",
        accuracy: float = 0.0,
        processing_time: float = 0.0,
        extracted_data: list | None = None,
        personality: Dict | None = None,
        attendance: Dict | None = None,
        error: str | None = None,
    ) -> None:
        self.id: str = document_id
        self.image_path: str = image_path
        self.status: str = status
        self.accuracy: float = accuracy
        self.processing_time: float = processing_time
        self.extracted_data: list = extracted_data or []
        self.personality: Optional[Dict] = personality
        self.attendance: Optional[Dict] = attendance
        self.error: Optional[str] = error

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for logging or legacy access."""
        return {
            "id": self.id,
            "status": self.status,
            "image_path": self.image_path,
            "accuracy": self.accuracy,
            "processing_time": self.processing_time,
            "extracted_data": self.extracted_data,
            "personality": self.personality,
            "attendance": self.attendance,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentRecord":
        return cls(
            document_id=data.get("id", ""),
            image_path=data.get("image_path", ""),
            status=data.get("status", "PROCESSING"),
            accuracy=data.get("accuracy", 0.0),
            processing_time=data.get("processing_time", 0.0),
            extracted_data=data.get("extracted_data", []),
            personality=data.get("personality"),
            attendance=data.get("attendance"),
            error=data.get("error"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentRecord":
        return cls.from_dict(json.loads(json_str))


class BaseDocumentStore(ABC):
    """Abstract interface for Document Stores."""

    @abstractmethod
    def create(self, document_id: str, image_path: str) -> DocumentRecord:
        pass

    @abstractmethod
    def get(self, document_id: str) -> Optional[DocumentRecord]:
        pass

    @abstractmethod
    def contains(self, document_id: str) -> bool:
        pass

    @abstractmethod
    def mark_success(
        self,
        document_id: str,
        extracted_data: list,
        personality: Optional[Dict],
        attendance: Optional[Dict],
        processing_time: float,
    ) -> None:
        pass

    @abstractmethod
    def mark_failed(
        self,
        document_id: str,
        error: str,
        processing_time: float,
    ) -> None:
        pass
