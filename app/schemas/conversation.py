from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]


class MessageCreate(BaseModel):
    message: str
    context_document_ids: list[int] = []


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    context_document_ids: list[int]
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""
    document_version_ids: list[int]
    prompt: str


class BatchAnalyzeResponse(BaseModel):
    """批量分析响应"""
    result: str
    document_count: int
    processing_time_ms: int | None = None
    history_id: int | None = None


class AnalysisRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_count: int
    prompt: str
    result: str
    source_documents: list[dict]
    created_at: datetime


class AnalysisRunListResponse(BaseModel):
    items: list[AnalysisRunSummaryResponse]


class AnalysisRunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_count: int
    prompt: str
    result: str
    context_text: str
    selected_document_version_ids: list[int]
    source_documents: list[dict]
    created_at: datetime
