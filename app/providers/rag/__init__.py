from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.repositories.knowledge_repository import DEFAULT_KNOWLEDGE_CHUNKS
from app.services.rag_retrieval import rank_knowledge_chunks


class RAGProvider(ABC):
    """Retrieval interface used by chat and audit report flows."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError


class StubRAGProvider(RAGProvider):
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return []


class LexicalRAGProvider(RAGProvider):
    """Deterministic local RAG provider backed by audit knowledge chunks."""

    def __init__(self, chunks: list[Any] | None = None) -> None:
        self.chunks = chunks or DEFAULT_KNOWLEDGE_CHUNKS

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return rank_knowledge_chunks(query, self.chunks, top_k=top_k)
