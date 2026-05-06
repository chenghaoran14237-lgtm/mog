from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InsightSessionCreateRequest(BaseModel):
    selected_document_version_ids: list[int]
    prompt: str


class InsightMessageCreateRequest(BaseModel):
    message: str


class InsightMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime


class InsightSessionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    selected_document_version_ids: list[int]
    source_documents: list[dict]
    created_at: datetime
    updated_at: datetime


class InsightSessionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    base_context_text: str
    selected_document_version_ids: list[int]
    source_documents: list[dict]
    created_at: datetime
    updated_at: datetime


class InsightSessionListResponse(BaseModel):
    items: list[InsightSessionSummaryResponse]


class InsightMessageListResponse(BaseModel):
    items: list[InsightMessageResponse]
