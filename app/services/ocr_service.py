from app.core.errors import APIError
from app.core.statuses import RecordStatus
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.ocr import OCRResultResponse
from app.services.provider_gateway import ProviderGateway


class OCRService:
    def __init__(
        self,
        record_repository: RecordRepository,
        ocr_result_repository: OCRResultRepository,
        provider_gateway: ProviderGateway,
    ) -> None:
        self.record_repository = record_repository
        self.ocr_result_repository = ocr_result_repository
        self.provider_gateway = provider_gateway

    def run_for_record_file(
        self,
        record_file_id: int,
        current_user_id: int,
        *,
        task_id: int | None = None,
        request_id: str | None = None,
    ) -> OCRResultResponse:
        record_file = self.record_repository.get_record_file_by_id(record_file_id, user_id=current_user_id)
        if record_file is None:
            raise APIError(status_code=404, code="record_file_not_found", message="Record file not found")

        self.record_repository.update_record_status(record_file.record_id, RecordStatus.OCR_PROCESSING)
        result = self.ocr_result_repository.create_processing(
            record_file_id=record_file.id,
            provider_name=self.provider_gateway.provider_registry.get_config("ocr").name,
        )
        try:
            extraction = self.provider_gateway.extract_ocr(
                user_id=current_user_id,
                task_id=task_id,
                request_id=request_id,
                resource_id=record_file.id,
                file_bytes=record_file.content_bytes,
                content_type=record_file.content_type,
            )
        except Exception:
            self.ocr_result_repository.mark_failed(result.id, error_code="provider_error")
            self.record_repository.update_record_status(record_file.record_id, RecordStatus.OCR_FAILED)
            raise

        raw_payload = extraction.raw_payload.copy()
        if extraction.block_payload is not None:
            raw_payload["block_payload"] = extraction.block_payload.model_dump()

        result = self.ocr_result_repository.mark_completed(
            ocr_result_id=result.id,
            provider_name=extraction.provider_name,
            raw_text=extraction.raw_text,
            raw_payload=raw_payload,
        )
        self.record_repository.update_record_status(record_file.record_id, RecordStatus.OCR_COMPLETED)
        return OCRResultResponse.model_validate(result)
