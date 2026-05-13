from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
from app.models.provider_event import ProviderEvent
from app.models.user import User
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    ProviderEventListResponse,
    ProviderEventSummaryItemResponse,
    ProviderEventSummaryResponse,
    TaskEventListResponse,
    TaskListResponse,
    TaskResponse,
    TaskResultResponse,
)
from app.services.task_service import TaskService
from app.tasks.runner import render_database_url, run_task

router = APIRouter(prefix="/tasks")


def build_task_service(session: Session) -> TaskService:
    return TaskService(
        task_repository=TaskRepository(session),
        record_repository=RecordRepository(session),
        ocr_result_repository=OCRResultRepository(session),
        extracted_document_repository=ExtractedDocumentRepository(session),
        document_version_repository=DocumentVersionRepository(session),
        measurement_repository=MeasurementRepository(session),
        provider_event_repository=ProviderEventRepository(session),
        provider_registry=ProviderRegistry(),
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    task_type: Literal["ocr", "normalization"] | None = None,
    status_value: Literal["pending", "processing", "completed", "failed"] | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskListResponse:
    service = build_task_service(session)
    return service.list_tasks(
        current_user_id=current_user.id,
        task_type=task_type,
        status_value=status_value,
    )


@router.get("/provider-events/summary", response_model=ProviderEventSummaryResponse)
def summarize_provider_events(
    window_hours: int = Query(default=24, ge=1, le=720),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ProviderEventSummaryResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    rows = session.execute(
        select(
            ProviderEvent.provider_type,
            ProviderEvent.provider_name,
            ProviderEvent.status,
            func.count(ProviderEvent.id),
            func.avg(ProviderEvent.duration_ms),
            func.max(ProviderEvent.created_at),
        )
        .where(ProviderEvent.user_id == current_user.id)
        .where(ProviderEvent.created_at >= cutoff)
        .group_by(ProviderEvent.provider_type, ProviderEvent.provider_name, ProviderEvent.status)
        .order_by(func.max(ProviderEvent.created_at).desc())
    ).all()

    return ProviderEventSummaryResponse(
        window_hours=window_hours,
        items=[
            ProviderEventSummaryItemResponse(
                provider_type=provider_type,
                provider_name=provider_name,
                status=status,
                event_count=int(event_count),
                avg_duration_ms=round(float(avg_duration_ms), 1) if avg_duration_ms is not None else None,
                last_event_at=last_event_at,
            )
            for provider_type, provider_name, status, event_count, avg_duration_ms, last_event_at in rows
        ],
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskResponse:
    service = build_task_service(session)
    return service.get_task(current_user_id=current_user.id, task_id=task_id)


@router.get("/{task_id}/events", response_model=TaskEventListResponse)
def list_task_events(
    task_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskEventListResponse:
    service = build_task_service(session)
    return service.list_task_events(current_user_id=current_user.id, task_id=task_id)


@router.get("/{task_id}/provider-events", response_model=ProviderEventListResponse)
def list_provider_events(
    task_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ProviderEventListResponse:
    service = build_task_service(session)
    return service.list_provider_events(current_user_id=current_user.id, task_id=task_id)


@router.get("/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(
    task_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskResultResponse:
    service = build_task_service(session)
    return service.get_task_result(current_user_id=current_user.id, task_id=task_id)


@router.post("/{task_id}/retry", response_model=TaskResponse)
def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskResponse:
    service = build_task_service(session)
    task = service.retry_task(
        current_user_id=current_user.id,
        task_id=task_id,
        request_id=getattr(request.state, "request_id", None),
    )
    background_tasks.add_task(
        run_task,
        task.id,
        task.request_id,
        render_database_url(session.get_bind().url),
    )
    return task
