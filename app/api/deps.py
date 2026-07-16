from functools import lru_cache

from app.core.config import settings
from app.infrastructure.storage.base import BaseDocumentStore
from app.infrastructure.storage.in_memory_store import InMemoryDocumentStore
from app.infrastructure.storage.redis_store import RedisDocumentStore


@lru_cache()
def get_document_store() -> BaseDocumentStore:
    """
    Dependency provider for the document store.
    Uses Redis if REDIS_URL is configured and non-empty,
    otherwise falls back to InMemory.
    """
    if settings.redis_url and settings.redis_url.strip():
        return RedisDocumentStore(redis_url=settings.redis_url)
    return InMemoryDocumentStore()
