from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
from app.core.db import SessionLocal
from app.models.user import User
from app.providers.registry import ProviderRegistry
from app.schemas.audit_report import (
    AuditReportCreateRequest,
    AuditReportEventResponse,
    AuditReportNodeStateResponse,
    AuditReportRunDetailResponse,
    AuditReportRunResponse,
)
from app.services.audit_report_service import AuditReportService

router = APIRouter(prefix="/audit-reports", tags=["audit-reports"])


def build_audit_report_service(session: Session, *, step_delay_seconds: float = 0.15) -> AuditReportService:
    return AuditReportService(
        session=session,
        llm_provider=ProviderRegistry().build_llm_provider(),
        step_delay_seconds=step_delay_seconds,
    )


@router.post("", response_model=AuditReportRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_audit_report_run(
    data: AuditReportCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> AuditReportRunResponse:
    service = build_audit_report_service(session)
    try:
        run = service.create_run(
            user_id=current_user.id,
            selected_document_version_ids=data.selected_document_version_ids,
            title=data.title,
            max_iterations=data.max_iterations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    background_tasks.add_task(_execute_audit_report_run, run.id, current_user.id)
    return run


@router.post("/{run_id}/execute", response_model=AuditReportRunResponse)
def execute_audit_report_run_now(
    run_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> AuditReportRunResponse:
    service = build_audit_report_service(session, step_delay_seconds=0)
    try:
        return service.execute_run(run_id=run_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=list[AuditReportRunResponse])
def list_audit_report_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[AuditReportRunResponse]:
    return build_audit_report_service(session).list_runs(user_id=current_user.id, limit=limit)


@router.get("/{run_id}", response_model=AuditReportRunDetailResponse)
def get_audit_report_run(
    run_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> AuditReportRunDetailResponse:
    service = build_audit_report_service(session)
    try:
        run = service.get_run(run_id=run_id, user_id=current_user.id)
        events = service.list_events(run_id=run_id, user_id=current_user.id)
        node_states = service.list_node_states(run_id=run_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AuditReportRunDetailResponse(run=run, events=events, node_states=node_states)


@router.get("/{run_id}/events", response_model=list[AuditReportEventResponse])
def list_audit_report_events(
    run_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[AuditReportEventResponse]:
    service = build_audit_report_service(session)
    try:
        return service.list_events(run_id=run_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{run_id}/nodes", response_model=list[AuditReportNodeStateResponse])
def list_audit_report_node_states(
    run_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> list[AuditReportNodeStateResponse]:
    service = build_audit_report_service(session)
    try:
        return service.list_node_states(run_id=run_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _execute_audit_report_run(run_id: int, user_id: int) -> None:
    session = SessionLocal()
    try:
        build_audit_report_service(session).execute_run(run_id=run_id, user_id=user_id)
    finally:
        session.close()
