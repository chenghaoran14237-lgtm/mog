from app.core.errors import APIError
from app.core.observability import log_event
from app.core.statuses import OCRStatus, TaskStatus, TaskType
from app.providers.errors import ProviderError
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.services.normalization_service import NormalizationService
from app.services.ocr_service import OCRService
from app.services.provider_gateway import ProviderGateway


class TaskProcessor:
    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        record_repository: RecordRepository,
        ocr_result_repository: OCRResultRepository,
        extracted_document_repository: ExtractedDocumentRepository,
        document_version_repository: DocumentVersionRepository,
        provider_event_repository: ProviderEventRepository,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.task_repository = task_repository
        self.record_repository = record_repository
        self.ocr_result_repository = ocr_result_repository
        self.extracted_document_repository = extracted_document_repository
        self.document_version_repository = document_version_repository
        self.provider_event_repository = provider_event_repository
        self.provider_registry = provider_registry

    def process_task(self, task_id: int, *, request_id: str | None = None) -> None:
        while True:
            task = self.task_repository.get_by_id(task_id)
            if task is None or task.status != TaskStatus.PENDING:
                return

            task = self.task_repository.mark_processing(task_id, request_id=request_id)
            log_event("task_processing", task_id=task.id, task_type=task.task_type, resource_id=task.resource_id)
            try:
                if task.task_type == TaskType.OCR:
                    self._process_ocr_task(task.id, request_id=request_id)
                elif task.task_type == TaskType.NORMALIZATION:
                    self._process_normalization_task(task.id, request_id=request_id)
                else:
                    raise ValueError(f"Unsupported task type: {task.task_type}")
                return
            except ProviderError as exc:
                if exc.retryable and task.attempt_count <= task.max_retries:
                    self.task_repository.schedule_retry(
                        task.id,
                        error_category=exc.category,
                        error_code=exc.code,
                        error_message=exc.message,
                        request_id=request_id,
                    )
                    log_event(
                        "task_retry_scheduled",
                        task_id=task.id,
                        error_code=exc.code,
                        attempt_count=task.attempt_count,
                    )
                    continue
                self.task_repository.mark_failed(
                    task.id,
                    error_category=exc.category,
                    error_code=exc.code,
                    error_message=exc.message,
                    retryable=exc.retryable,
                    request_id=request_id,
                )
                log_event("task_failed", task_id=task.id, error_code=exc.code, detail=exc.message)
                return
            except APIError as exc:
                self.task_repository.mark_failed(
                    task.id,
                    error_category="application_error",
                    error_code=exc.code,
                    error_message=exc.message,
                    retryable=False,
                    request_id=request_id,
                )
                log_event("task_failed", task_id=task.id, error_code=exc.code, detail=exc.message)
                return
            except Exception as exc:
                self.task_repository.mark_failed(
                    task.id,
                    error_category="internal_error",
                    error_code="task_execution_failed",
                    error_message=str(exc),
                    retryable=False,
                    request_id=request_id,
                )
                log_event("task_failed", task_id=task.id, error_code="task_execution_failed", detail=str(exc))
                return

    def _process_ocr_task(self, task_id: int, *, request_id: str | None) -> None:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found")
        force_reprocess = bool(task.task_payload.get("force_reprocess"))

        existing_result = self.ocr_result_repository.get_current_for_record_file(
            task.resource_id,
            user_id=task.user_id,
        )
        if existing_result is not None and not force_reprocess:
            self.task_repository.mark_completed(
                task.id,
                result_resource_type="ocr_result",
                result_resource_id=existing_result.id,
                request_id=request_id,
            )
            log_event("task_completed_reused_result", task_id=task.id, result_resource_id=existing_result.id)
            return

        service = OCRService(
            record_repository=self.record_repository,
            ocr_result_repository=self.ocr_result_repository,
            provider_gateway=ProviderGateway(
                provider_registry=self.provider_registry,
                provider_event_repository=self.provider_event_repository,
            ),
        )
        response = service.run_for_record_file(
            task.resource_id,
            current_user_id=task.user_id,
            task_id=task.id,
            request_id=request_id,
        )
        self.task_repository.mark_completed(
            task.id,
            result_resource_type="ocr_result",
            result_resource_id=response.id,
            request_id=request_id,
        )
        log_event("task_completed", task_id=task.id, result_resource_id=response.id)

    def _process_normalization_task(self, task_id: int, *, request_id: str | None) -> None:
        task = self.task_repository.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found")
        force_reprocess = bool(task.task_payload.get("force_reprocess"))
        ocr_result = self.ocr_result_repository.get_by_id(task.resource_id, user_id=task.user_id)
        if ocr_result is None:
            raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")

        existing_document = self.extracted_document_repository.get_by_record_file_id(
            ocr_result.record_file_id,
            user_id=task.user_id,
        )
        if not force_reprocess and existing_document is not None:
            current_version = self.document_version_repository.get_current_for_document(existing_document.id, user_id=task.user_id)
            if current_version is not None and existing_document.current_ocr_result_id == task.resource_id:
                task.task_payload = {**task.task_payload, "version_created": False}
                self.task_repository.session.commit()
                self.task_repository.mark_completed(
                    task.id,
                    result_resource_type="document_version",
                    result_resource_id=current_version.id,
                    request_id=request_id,
                )
                log_event("task_completed_reused_result", task_id=task.id, result_resource_id=current_version.id)
                return

        service = NormalizationService(
            ocr_result_repository=self.ocr_result_repository,
            record_repository=self.record_repository,
            extracted_document_repository=self.extracted_document_repository,
            document_version_repository=self.document_version_repository,
            provider_gateway=ProviderGateway(
                provider_registry=self.provider_registry,
                provider_event_repository=self.provider_event_repository,
            ),
        )
        response = service.normalize_ocr_result(
            task.resource_id,
            current_user_id=task.user_id,
            task_id=task.id,
            request_id=request_id,
            allow_reprocess=force_reprocess,
        )
        task.task_payload = {**task.task_payload, "version_created": response.version_created}
        self.task_repository.session.commit()
        self.task_repository.mark_completed(
            task.id,
            result_resource_type="document_version",
            result_resource_id=response.version.id,
            request_id=request_id,
        )
        log_event("task_completed", task_id=task.id, result_resource_id=response.version.id)
        return

