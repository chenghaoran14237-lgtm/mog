import time

from app.core.observability import log_event
from app.providers.base import NormalizationResult, OCRExtractionResult, StorageWriteResult
from app.providers.errors import ProviderConfigurationError, ProviderError, ProviderNonRetryableError
from app.providers.registry import ProviderRegistry
from app.repositories.provider_event_repository import ProviderEventRepository


class ProviderGateway:
    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        provider_event_repository: ProviderEventRepository,
    ) -> None:
        self.provider_registry = provider_registry
        self.provider_event_repository = provider_event_repository

    def store_file(
        self,
        *,
        user_id: int,
        task_id: int | None,
        request_id: str | None,
        resource_id: int,
        original_filename: str,
        content_type: str | None,
        content_bytes: bytes,
    ) -> StorageWriteResult:
        return self._execute(
            provider_type="storage",
            operation="store_file",
            user_id=user_id,
            task_id=task_id,
            request_id=request_id,
            resource_type="record_file",
            resource_id=resource_id,
            runner=lambda: self.provider_registry.build_storage_provider().store(
                content_bytes=content_bytes,
                content_type=content_type,
                original_filename=original_filename,
            ),
        )

    def extract_ocr(
        self,
        *,
        user_id: int,
        task_id: int | None,
        request_id: str | None,
        resource_id: int,
        file_bytes: bytes,
        content_type: str | None,
    ) -> OCRExtractionResult:
        return self._execute(
            provider_type="ocr",
            operation="extract",
            user_id=user_id,
            task_id=task_id,
            request_id=request_id,
            resource_type="record_file",
            resource_id=resource_id,
            runner=lambda: self.provider_registry.build_ocr_provider().extract(
                file_bytes=file_bytes,
                content_type=content_type,
            ),
        )

    def normalize(
        self,
        *,
        user_id: int,
        task_id: int | None,
        request_id: str | None,
        resource_id: int,
        raw_text: str,
    ) -> NormalizationResult:
        return self._execute(
            provider_type="normalization",
            operation="normalize",
            user_id=user_id,
            task_id=task_id,
            request_id=request_id,
            resource_type="ocr_result",
            resource_id=resource_id,
            runner=lambda: self.provider_registry.build_normalization_provider().normalize(raw_text),
        )

    def _execute(
        self,
        *,
        provider_type: str,
        operation: str,
        user_id: int | None,
        task_id: int | None,
        request_id: str | None,
        resource_type: str,
        resource_id: int,
        runner,
    ):
        started = time.perf_counter()
        try:
            config = self.provider_registry.get_config(provider_type)
            result = runner()
        except ProviderError as exc:
            self._record_event(
                task_id=task_id,
                user_id=user_id,
                provider_type=provider_type,
                provider_name=exc.provider_name,
                operation=operation,
                resource_type=resource_type,
                resource_id=resource_id,
                status="failed",
                error_category=exc.category,
                error_code=exc.code,
                retryable=exc.retryable,
                duration_ms=self._duration_ms(started),
                request_id=request_id,
                payload=exc.details,
            )
            log_event(
                "provider_call_failed",
                provider_type=provider_type,
                provider_name=exc.provider_name,
                operation=operation,
                error_code=exc.code,
                retryable=exc.retryable,
            )
            raise
        except Exception as exc:
            error = ProviderNonRetryableError(
                provider_type=provider_type,
                provider_name=config.name,
                code="unexpected_provider_error",
                message=str(exc),
                details={},
            )
            self._record_event(
                task_id=task_id,
                user_id=user_id,
                provider_type=provider_type,
                provider_name=config.name,
                operation=operation,
                resource_type=resource_type,
                resource_id=resource_id,
                status="failed",
                error_category=error.category,
                error_code=error.code,
                retryable=error.retryable,
                duration_ms=self._duration_ms(started),
                request_id=request_id,
                payload={},
            )
            log_event(
                "provider_call_failed",
                provider_type=provider_type,
                provider_name=config.name,
                operation=operation,
                error_code=error.code,
                retryable=error.retryable,
            )
            raise error from exc

        provider_name = getattr(result, "provider_name", config.name)
        self._record_event(
            task_id=task_id,
            user_id=user_id,
            provider_type=provider_type,
            provider_name=provider_name,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            status="completed",
            error_category=None,
            error_code=None,
            retryable=False,
            duration_ms=self._duration_ms(started),
            request_id=request_id,
            payload={},
        )
        log_event(
            "provider_call_completed",
            provider_type=provider_type,
            provider_name=provider_name,
            operation=operation,
        )
        return result

    def _record_event(
        self,
        *,
        task_id: int | None,
        user_id: int | None,
        provider_type: str,
        provider_name: str,
        operation: str,
        resource_type: str,
        resource_id: int,
        status: str,
        error_category: str | None,
        error_code: str | None,
        retryable: bool,
        duration_ms: int,
        request_id: str | None,
        payload: dict,
    ) -> None:
        self.provider_event_repository.create_event(
            task_id=task_id,
            user_id=user_id,
            provider_type=provider_type,
            provider_name=provider_name,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_category=error_category,
            error_code=error_code,
            retryable=retryable,
            duration_ms=duration_ms,
            request_id=request_id,
            payload=payload,
        )

    def _duration_ms(self, started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
