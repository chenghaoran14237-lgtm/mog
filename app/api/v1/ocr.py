from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
from app.models.user import User
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.ocr import OCRResultListResponse, OCRResultResponse, OCRRevisionDiffResponse
from app.schemas.task import TaskSubmissionResponse
from app.services.ocr_query_service import OCRQueryService
from app.services.task_service import TaskService
from app.tasks.runner import render_database_url, run_task

router = APIRouter(prefix="/ocr")


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


def build_ocr_query_service(session: Session) -> OCRQueryService:
    return OCRQueryService(
        record_repository=RecordRepository(session),
        ocr_result_repository=OCRResultRepository(session),
    )


@router.post("/files/{record_file_id}/extract", response_model=TaskSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
def extract_ocr(
    record_file_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    force: bool = Query(default=False),
    sync: bool = Query(default=True, description="同步执行任务（开发模式推荐）"),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskSubmissionResponse:
    service = build_task_service(session)
    submission = service.submit_ocr_task(
        current_user_id=current_user.id,
        record_file_id=record_file_id,
        request_id=getattr(request.state, "request_id", None),
        force_reprocess=force,
    )

    if submission.task.status == "pending":
        if sync:
            from app.services.task_processor import TaskProcessor

            print(f"[SYNC] Executing OCR task {submission.task.id} synchronously")

            processor = TaskProcessor(
                task_repository=TaskRepository(session),
                record_repository=RecordRepository(session),
                ocr_result_repository=OCRResultRepository(session),
                extracted_document_repository=ExtractedDocumentRepository(session),
                document_version_repository=DocumentVersionRepository(session),
                provider_event_repository=ProviderEventRepository(session),
                provider_registry=ProviderRegistry(),
            )

            try:
                processor.process_task(submission.task.id, request_id=submission.task.request_id)
                session.commit()
                print(f"[SYNC] OCR task {submission.task.id} completed")
            except Exception as exc:
                session.rollback()
                print(f"[SYNC] OCR task {submission.task.id} failed: {exc}")
                raise
        else:
            background_tasks.add_task(
                run_task,
                submission.task.id,
                submission.task.request_id,
                render_database_url(session.get_bind().url),
            )

    return submission


@router.get("/files/{record_file_id}/revisions", response_model=OCRResultListResponse)
def list_ocr_revisions(
    record_file_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "id", "revision_number"] = "revision_number",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> OCRResultListResponse:
    service = build_ocr_query_service(session)
    return service.list_revisions_for_file(
        record_file_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/files/{record_file_id}/revisions/current", response_model=OCRResultResponse)
def get_current_ocr_revision(
    record_file_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> OCRResultResponse:
    service = build_ocr_query_service(session)
    return service.get_current_revision_for_file(record_file_id, current_user_id=current_user.id)


@router.get("/revisions/compare", response_model=OCRRevisionDiffResponse)
def compare_ocr_revisions(
    from_id: int = Query(..., ge=1),
    to_id: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> OCRRevisionDiffResponse:
    service = build_ocr_query_service(session)
    return service.compare_revisions(from_id, to_id, current_user_id=current_user.id)


@router.get("/revisions/{ocr_result_id}", response_model=OCRResultResponse)
def get_ocr_revision(
    ocr_result_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> OCRResultResponse:
    service = build_ocr_query_service(session)
    return service.get_revision(ocr_result_id, current_user_id=current_user.id)
