from datetime import datetime

from fastapi import status

from app.core.errors import APIError
from app.core.statuses import OCRStatus, TaskStatus, TaskType
from app.providers.registry import ProviderRegistry
from app.models.task import Task
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.ingestion import DocumentVersionResponse, ExtractedDocumentResponse, MeasurementResponse, NormalizeOCRResponse
from app.schemas.ocr import OCRResultResponse
from app.schemas.task import (
    ProviderEventListResponse,
    ProviderEventResponse,
    TaskEventListResponse,
    TaskEventResponse,
    TaskListResponse,
    TaskResponse,
    TaskResultResponse,
    TaskSubmissionResponse,
)


class TaskService:
    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        record_repository: RecordRepository,
        ocr_result_repository: OCRResultRepository,
        extracted_document_repository: ExtractedDocumentRepository,
        document_version_repository: DocumentVersionRepository,
        measurement_repository: MeasurementRepository,
        provider_event_repository: ProviderEventRepository,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.task_repository = task_repository
        self.record_repository = record_repository
        self.ocr_result_repository = ocr_result_repository
        self.extracted_document_repository = extracted_document_repository
        self.document_version_repository = document_version_repository
        self.measurement_repository = measurement_repository
        self.provider_event_repository = provider_event_repository
        self.provider_registry = provider_registry

    def submit_ocr_task(
        self,
        *,
        current_user_id: int,
        record_file_id: int,
        request_id: str | None,
        force_reprocess: bool = False,
        batch_id: str | None = None,
        priority: int = 5,
    ) -> TaskSubmissionResponse:
        record_file = self.record_repository.get_record_file_by_id(record_file_id, user_id=current_user_id)
        if record_file is None:
            raise APIError(status_code=404, code="record_file_not_found", message="Record file not found")
        return self._submit_task(
            current_user_id=current_user_id,
            task_type=TaskType.OCR,
            resource_type="record_file",
            resource_id=record_file_id,
            request_id=request_id,
            max_retries=self.provider_registry.get_config("ocr").max_retries,
            reuse_completed=not force_reprocess,
            task_payload={"force_reprocess": force_reprocess},
            batch_id=batch_id,
            priority=priority,
        )

    def submit_normalization_task(
        self,
        *,
        current_user_id: int,
        ocr_result_id: int,
        request_id: str | None,
        force_reprocess: bool = False,
        batch_id: str | None = None,
        priority: int = 5,
    ) -> TaskSubmissionResponse:
        ocr_result = self.ocr_result_repository.get_by_id(ocr_result_id, user_id=current_user_id)
        if ocr_result is None:
            raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")
        if ocr_result.status != OCRStatus.COMPLETED:
            raise APIError(
                status_code=409,
                code="ocr_result_not_ready",
                message="OCR result is not ready for normalization",
            )
        return self._submit_task(
            current_user_id=current_user_id,
            task_type=TaskType.NORMALIZATION,
            resource_type="ocr_result",
            resource_id=ocr_result_id,
            request_id=request_id,
            max_retries=self.provider_registry.get_config("normalization").max_retries,
            reuse_completed=not force_reprocess,
            task_payload={"force_reprocess": force_reprocess, "trigger_reason": "manual" if force_reprocess else "initial"},
            batch_id=batch_id,
            priority=priority,
        )

    def list_tasks(
        self,
        *,
        current_user_id: int,
        task_type: str | None = None,
        status_value: str | None = None,
        batch_id: str | None = None,
    ) -> TaskListResponse:
        tasks = self.task_repository.list_tasks(
            user_id=current_user_id,
            task_type=task_type,
            status=status_value,
            batch_id=batch_id,
        )
        return TaskListResponse(items=[self._build_task_response(task) for task in tasks])

    def get_tasks_by_batch(self, *, user_id: int, batch_id: str) -> list[Task]:
        """获取批量任务列表"""
        return self.task_repository.list_tasks(user_id=user_id, batch_id=batch_id)

    def get_task(self, *, current_user_id: int, task_id: int) -> TaskResponse:
        task = self.task_repository.get_by_id(task_id, user_id=current_user_id)
        if task is None:
            raise APIError(status_code=404, code="task_not_found", message="Task not found")
        return self._build_task_response(task)

    def list_task_events(self, *, current_user_id: int, task_id: int) -> TaskEventListResponse:
        task = self.task_repository.get_by_id(task_id, user_id=current_user_id)
        if task is None:
            raise APIError(status_code=404, code="task_not_found", message="Task not found")
        events = self.task_repository.list_events(task_id)
        return TaskEventListResponse(
            items=[
                TaskEventResponse(
                    id=event.id,
                    event_type=event.event_type,
                    from_status=event.from_status,
                    to_status=event.to_status,
                    request_id=event.request_id,
                    message=event.message,
                    payload=event.payload,
                    created_at=event.created_at,
                )
                for event in events
            ]
        )

    def list_provider_events(self, *, current_user_id: int, task_id: int) -> ProviderEventListResponse:
        task = self.task_repository.get_by_id(task_id, user_id=current_user_id)
        if task is None:
            raise APIError(status_code=404, code="task_not_found", message="Task not found")
        events = self.provider_event_repository.list_for_task(task_id)
        return ProviderEventListResponse(
            items=[
                ProviderEventResponse(
                    id=event.id,
                    provider_type=event.provider_type,
                    provider_name=event.provider_name,
                    operation=event.operation,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    status=event.status,
                    error_category=event.error_category,
                    error_code=event.error_code,
                    retryable=event.retryable,
                    duration_ms=event.duration_ms,
                    request_id=event.request_id,
                    payload=event.payload,
                    created_at=event.created_at,
                )
                for event in events
            ]
        )

    def retry_task(
        self,
        *,
        current_user_id: int,
        task_id: int,
        request_id: str | None,
    ) -> TaskResponse:
        task = self.task_repository.get_by_id(task_id, user_id=current_user_id)
        if task is None:
            raise APIError(status_code=404, code="task_not_found", message="Task not found")
        if task.status != TaskStatus.FAILED:
            raise APIError(status_code=409, code="task_not_retryable", message="Task is not retryable")
        if not task.last_error_retryable:
            raise APIError(status_code=409, code="task_not_retryable", message="Task is not retryable")
        if task.attempt_count > task.max_retries:
            raise APIError(status_code=409, code="task_retry_limit_reached", message="Task retry limit reached")
        task = self.task_repository.reset_for_retry(task_id, request_id=request_id)
        return self._build_task_response(task)

    def get_task_result(self, *, current_user_id: int, task_id: int) -> TaskResultResponse:
        task = self.task_repository.get_by_id(task_id, user_id=current_user_id)
        if task is None:
            raise APIError(status_code=404, code="task_not_found", message="Task not found")
        if task.status != TaskStatus.COMPLETED:
            raise APIError(status_code=409, code="task_not_completed", message="Task has not completed")
        if task.result_resource_type is None or task.result_resource_id is None:
            raise APIError(status_code=409, code="task_result_unavailable", message="Task result is unavailable")

        if task.result_resource_type == "ocr_result":
            result = self.ocr_result_repository.get_by_id(task.result_resource_id, user_id=current_user_id)
            if result is None:
                raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")
            data = OCRResultResponse.model_validate(result).model_dump(mode="json")
        elif task.result_resource_type == "document_version":
            version = self.document_version_repository.get_by_id(task.result_resource_id, user_id=current_user_id)
            if version is None:
                raise APIError(status_code=404, code="document_version_not_found", message="Document version not found")
            document = self.extracted_document_repository.get_by_id(version.document_id, user_id=current_user_id)
            if document is None:
                raise APIError(status_code=404, code="document_not_found", message="Extracted document not found")
            measurements = [MeasurementResponse.model_validate(row) for row in sorted(version.measurements, key=lambda item: item.id)]
            data = NormalizeOCRResponse(
                document=ExtractedDocumentResponse.model_validate(document),
                version=DocumentVersionResponse.model_validate(version),
                measurements=measurements,
                version_created=bool(task.task_payload.get("version_created", True)),
            ).model_dump(mode="json")
        else:
            raise APIError(status_code=409, code="task_result_unavailable", message="Task result is unavailable")

        return TaskResultResponse(
            task=self._build_task_response(task),
            result_type=task.result_resource_type,
            data=data,
        )

    def _submit_task(
        self,
        *,
        current_user_id: int,
        task_type: str,
        resource_type: str,
        resource_id: int,
        request_id: str | None,
        max_retries: int,
        reuse_completed: bool = True,
        task_payload: dict | None = None,
        batch_id: str | None = None,
        priority: int = 5,
    ) -> TaskSubmissionResponse:
        active_task = self.task_repository.find_active_task(
            user_id=current_user_id,
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if active_task is not None and self._is_stale_pending_task(active_task):
            self.task_repository.mark_failed(
                active_task.id,
                error_category="internal_error",
                error_code="task_dispatch_stalled",
                error_message="Task stayed pending and was replaced by a new submission",
                retryable=True,
                request_id=request_id,
            )
            active_task = None
        if active_task is not None:
            self.task_repository.create_event(
                task_id=active_task.id,
                event_type="task_reused",
                from_status=active_task.status,
                to_status=active_task.status,
                request_id=request_id,
                message="Existing active task reused",
                payload={},
            )
            self.task_repository.session.commit()
            self.task_repository.session.refresh(active_task)
            return TaskSubmissionResponse(task=self._build_task_response(active_task), created=False)

        terminal_task = self.task_repository.find_latest_terminal_task(
            user_id=current_user_id,
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if terminal_task is not None and terminal_task.status == TaskStatus.COMPLETED and reuse_completed:
            self.task_repository.create_event(
                task_id=terminal_task.id,
                event_type="task_reused",
                from_status=terminal_task.status,
                to_status=terminal_task.status,
                request_id=request_id,
                message="Existing completed task reused",
                payload={},
            )
            self.task_repository.session.commit()
            self.task_repository.session.refresh(terminal_task)
            return TaskSubmissionResponse(task=self._build_task_response(terminal_task), created=False)
        task = self.task_repository.create_task(
            user_id=current_user_id,
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            max_retries=max_retries,
            task_payload=task_payload,
            batch_id=batch_id,
            priority=priority,
        )
        return TaskSubmissionResponse(task=self._build_task_response(task), created=True)

    def _is_stale_pending_task(self, task: Task) -> bool:
        if task.status != TaskStatus.PENDING or task.started_at is not None:
            return False
        created_at = task.created_at
        now = datetime.now(created_at.tzinfo) if created_at.tzinfo is not None else datetime.now()
        return (now - created_at).total_seconds() >= 15

    def _build_task_response(self, task: Task) -> TaskResponse:
        return TaskResponse(
            id=task.id,
            task_type=task.task_type,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            status=task.status,
            request_id=task.request_id,
            attempt_count=task.attempt_count,
            max_retries=task.max_retries,
            result_resource_type=task.result_resource_type,
            result_resource_id=task.result_resource_id,
            last_error_code=task.last_error_code,
            last_error_message=task.last_error_message,
            last_error_category=task.last_error_category,
            last_error_retryable=task.last_error_retryable,
            started_at=task.started_at,
            completed_at=task.completed_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
