from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    source_type: str
    source_title: str
    section_title: str
    content: str
    keywords: list[str]
    tags: list[str]
    metadata_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchResultResponse(BaseModel):
    id: int | str | None
    scope: str
    source_type: str
    source_title: str
    section_title: str
    content: str
    keywords: list[str]
    tags: list[str]
    metadata_json: dict[str, Any]
    score: float
    retrieval_method: str
    score_breakdown: dict[str, float]
    matched_terms: list[str]


class KnowledgeSourceSummaryResponse(BaseModel):
    source_name: str
    source_url: str
    source_type: str
    source_title: str
    source_language: str | None = None
    evidence_level: str | None = None
    source_retrieved_at: str | None = None
    chunk_count: int
    sections: list[str]
