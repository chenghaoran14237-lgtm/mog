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
from app.schemas.task import TaskSubmissionResponse
from app.services.task_service import TaskService
from app.tasks.runner import render_database_url, run_task

router = APIRouter(prefix="/ingestion")


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


@router.post(
    "/ocr-results/{ocr_result_id}/normalize",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def normalize_ocr_result(
    ocr_result_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    force: bool = Query(default=False),
    sync: bool = Query(default=True, description="同步执行任务（开发模式推荐）"),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> TaskSubmissionResponse:
    service = build_task_service(session)
    submission = service.submit_normalization_task(
        current_user_id=current_user.id,
        ocr_result_id=ocr_result_id,
        request_id=getattr(request.state, "request_id", None),
        force_reprocess=force,
    )

    if submission.task.status == "pending":
        if sync:
            from app.services.task_processor import TaskProcessor

            print(f"[SYNC] Executing normalization task {submission.task.id} synchronously")

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
                print(f"[SYNC] Normalization task {submission.task.id} completed")
            except Exception as exc:
                session.rollback()
                print(f"[SYNC] Normalization task {submission.task.id} failed: {exc}")
                raise
        else:
            background_tasks.add_task(
                run_task,
                submission.task.id,
                submission.task.request_id,
                render_database_url(session.get_bind().url),
            )

    return submission
