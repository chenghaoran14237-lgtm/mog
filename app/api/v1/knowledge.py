from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
from app.models.user import User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    KnowledgeChunkResponse,
    KnowledgeSearchResultResponse,
    KnowledgeSourceSummaryResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/chunks", response_model=list[KnowledgeChunkResponse])
def list_knowledge_chunks(
    scope: str = Query(default="medical_audit", min_length=1, max_length=50),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[KnowledgeChunkResponse]:
    del current_user
    return KnowledgeRepository(session).ensure_default_chunks(scope=scope)


@router.get("/sources", response_model=list[KnowledgeSourceSummaryResponse])
def list_knowledge_sources(
    scope: str = Query(default="medical_audit", min_length=1, max_length=50),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[KnowledgeSourceSummaryResponse]:
    del current_user
    return KnowledgeRepository(session).list_source_summaries(scope=scope)


@router.get("/search", response_model=list[KnowledgeSearchResultResponse])
def search_knowledge(
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    scope: str = Query(default="medical_audit", min_length=1, max_length=50),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[KnowledgeSearchResultResponse]:
    del current_user
    return KnowledgeRepository(session).search(query=query, top_k=top_k, scope=scope)
