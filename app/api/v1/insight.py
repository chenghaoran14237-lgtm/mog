from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.providers.errors import ProviderError
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.schemas.insight import (
    InsightMessageCreateRequest,
    InsightMessageListResponse,
    InsightMessageResponse,
    InsightSessionCreateRequest,
    InsightSessionDetailResponse,
    InsightSessionListResponse,
    InsightSessionSummaryResponse,
)
from app.services.analysis_fallback import build_health_analysis_fallback
from app.services.conversation_context_service import ConversationContextService
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insight", tags=["insight"])


def get_insight_service(session: Session = Depends(get_session)) -> InsightService:
    llm_provider = ProviderRegistry().build_llm_provider()
    document_version_repo = DocumentVersionRepository(session)
    measurement_repo = MeasurementRepository(session)
    context_service = ConversationContextService(document_version_repo, measurement_repo)
    return InsightService(
        session,
        llm_provider=llm_provider,
        document_version_repo=document_version_repo,
        context_service=context_service,
    )


def _event(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


@router.get("/sessions", response_model=InsightSessionListResponse)
def list_sessions(
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    items = insight_service.list_sessions(user_id=current_user.id)
    return InsightSessionListResponse(
        items=[InsightSessionSummaryResponse.model_validate(item) for item in items]
    )


@router.get("/sessions/{session_id}", response_model=InsightSessionDetailResponse)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    insight_session = insight_service.get_session(user_id=current_user.id, session_id=session_id)
    if insight_session is None:
        raise HTTPException(status_code=404, detail="Insight session not found")
    return InsightSessionDetailResponse.model_validate(insight_session)


@router.get("/sessions/{session_id}/messages", response_model=InsightMessageListResponse)
def list_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    insight_session = insight_service.get_session(user_id=current_user.id, session_id=session_id)
    if insight_session is None:
        raise HTTPException(status_code=404, detail="Insight session not found")
    return InsightMessageListResponse(
        items=[InsightMessageResponse.model_validate(item) for item in insight_session.messages]
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    deleted = insight_service.delete_session(user_id=current_user.id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Insight session not found")


@router.post("/sessions/stream")
def create_session_stream(
    data: InsightSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    def generate():
        try:
            insight_session, _ = insight_service.create_session(
                user_id=current_user.id,
                selected_document_version_ids=data.selected_document_version_ids,
                prompt=data.prompt,
            )
            messages = insight_service.build_llm_messages_for_session(insight_session=insight_session)
            yield _event(
                {
                    "type": "meta",
                    "session_id": insight_session.id,
                    "title": insight_session.title,
                    "document_count": len(insight_session.selected_document_version_ids),
                }
            )

            chunks: list[str] = []
            try:
                for chunk in insight_service.llm_provider.stream_chat(messages=messages, temperature=0.7):
                    if chunk:
                        chunks.append(chunk)
                        yield _event({"type": "delta", "content": chunk})
            except ProviderError as exc:
                fallback = build_health_analysis_fallback(
                    prompt=data.prompt,
                    context_text=insight_session.base_context_text,
                    document_count=len(insight_session.selected_document_version_ids),
                    reason=exc.message,
                )
                chunks.append(fallback)
                yield _event({"type": "delta", "content": fallback})

            assistant = insight_service.append_assistant_message(
                user_id=current_user.id,
                session_id=insight_session.id,
                content="".join(chunks),
            )
            yield _event(
                {
                    "type": "done",
                    "session_id": insight_session.id,
                    "assistant_message_id": assistant.id,
                }
            )
        except ValueError as exc:
            yield _event({"type": "error", "message": str(exc)})

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/sessions/{session_id}/messages/stream")
def create_message_stream(
    session_id: int,
    data: InsightMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    insight_service: InsightService = Depends(get_insight_service),
):
    def generate():
        try:
            insight_session, _ = insight_service.append_user_message(
                user_id=current_user.id,
                session_id=session_id,
                content=data.message,
            )
            messages = insight_service.build_llm_messages_for_session(insight_session=insight_session)
            yield _event({"type": "meta", "session_id": session_id, "title": insight_session.title})

            chunks: list[str] = []
            try:
                for chunk in insight_service.llm_provider.stream_chat(messages=messages, temperature=0.7):
                    if chunk:
                        chunks.append(chunk)
                        yield _event({"type": "delta", "content": chunk})
            except ProviderError as exc:
                fallback = build_health_analysis_fallback(
                    prompt=data.message,
                    context_text=insight_session.base_context_text,
                    document_count=len(insight_session.selected_document_version_ids),
                    reason=exc.message,
                )
                chunks.append(fallback)
                yield _event({"type": "delta", "content": fallback})

            assistant = insight_service.append_assistant_message(
                user_id=current_user.id,
                session_id=session_id,
                content="".join(chunks),
            )
            yield _event(
                {
                    "type": "done",
                    "session_id": session_id,
                    "assistant_message_id": assistant.id,
                }
            )
        except ValueError as exc:
            yield _event({"type": "error", "message": str(exc)})

    return StreamingResponse(generate(), media_type="application/x-ndjson")
