import hashlib
import json

from app.core.errors import APIError
from app.core.statuses import NormalizationStatus, OCRStatus, RecordStatus
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.ingestion import (
    DocumentVersionResponse,
    ExtractedDocumentResponse,
    MeasurementResponse,
    NormalizeOCRResponse,
)
from app.services.provider_gateway import ProviderGateway


class NormalizationService:
    def __init__(
        self,
        ocr_result_repository: OCRResultRepository,
        record_repository: RecordRepository,
        extracted_document_repository: ExtractedDocumentRepository,
        document_version_repository: DocumentVersionRepository,
        provider_gateway: ProviderGateway,
    ) -> None:
        self.ocr_result_repository = ocr_result_repository
        self.record_repository = record_repository
        self.extracted_document_repository = extracted_document_repository
        self.document_version_repository = document_version_repository
        self.provider_gateway = provider_gateway

    def normalize_ocr_result(
        self,
        ocr_result_id: int,
        current_user_id: int,
        *,
        task_id: int | None = None,
        request_id: str | None = None,
        allow_reprocess: bool = False,
    ) -> NormalizeOCRResponse:
        ocr_result = self.ocr_result_repository.get_by_id(ocr_result_id, user_id=current_user_id)
        if ocr_result is None:
            raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")
        if ocr_result.status != OCRStatus.COMPLETED:
            raise APIError(status_code=409, code="ocr_result_not_ready", message="OCR result is not ready for normalization")

        record_file = self.record_repository.get_record_file_by_id(ocr_result.record_file_id, user_id=current_user_id)
        if record_file is None:
            raise APIError(status_code=404, code="record_file_not_found", message="Record file not found")

        document = self.extracted_document_repository.get_or_create_document(
            ocr_result_id=ocr_result.id,
            record_id=record_file.record_id,
            record_file_id=record_file.id,
            document_type="generic_record",
            display_name=record_file.display_name,
        )
        current_version = self.document_version_repository.get_current_for_document(document.id)
        same_current_revision = current_version is not None and document.current_ocr_result_id == ocr_result.id
        if same_current_revision and not allow_reprocess:
            raise APIError(status_code=409, code="ocr_result_already_normalized", message="OCR result already normalized")

        self.extracted_document_repository.update_projection(
            document.id,
            status=NormalizationStatus.PROCESSING,
            normalized_payload=document.normalized_payload,
            current_ocr_result_id=ocr_result.id,
        )
        self.record_repository.update_record_status(record_file.record_id, RecordStatus.NORMALIZATION_PROCESSING)
        try:
            normalization_result = self.provider_gateway.normalize(
                user_id=current_user_id,
                task_id=task_id,
                request_id=request_id,
                resource_id=ocr_result.id,
                raw_text=ocr_result.raw_text,
            )
            snapshot_hash = self._build_snapshot_hash(normalization_result)
        except Exception:
            self.extracted_document_repository.update_projection(
                document.id,
                status=NormalizationStatus.FAILED,
                normalized_payload={"error": "normalization_failed"},
                current_ocr_result_id=document.current_ocr_result_id,
            )
            self.record_repository.update_record_status(record_file.record_id, RecordStatus.NORMALIZATION_FAILED)
            raise

        should_create_version = (
            current_version is None
            or current_version.created_from_ocr_result_id != ocr_result.id
            or current_version.snapshot_hash != snapshot_hash
        )

        if not should_create_version:
            version = current_version
            measurement_rows = sorted(version.measurements, key=lambda item: item.id)
            version_created = False
        else:
            version, measurement_rows = self.document_version_repository.create_version(
                document_id=document.id,
                created_from_ocr_result_id=ocr_result.id,
                snapshot_hash=snapshot_hash,
                report_date=normalization_result.report_date,
                normalized_payload=normalization_result.normalized_payload,
                measurements=normalization_result.measurements,
            )
            version_created = True

        document = self.extracted_document_repository.update_projection(
            document.id,
            status=NormalizationStatus.NORMALIZED,
            normalized_payload=version.normalized_payload,
            document_type=normalization_result.document_type,
            document_category=normalization_result.document_category,
            report_date=normalization_result.report_date,
            current_ocr_result_id=ocr_result.id,
        )
        self.record_repository.update_record_status(record_file.record_id, RecordStatus.NORMALIZED)
        return NormalizeOCRResponse(
            document=ExtractedDocumentResponse.model_validate(document),
            version=DocumentVersionResponse.model_validate(version),
            measurements=[MeasurementResponse.model_validate(row) for row in measurement_rows],
            version_created=version_created,
        )

    def _build_snapshot_hash(self, normalization_result) -> str:
        payload = {
            "document_type": normalization_result.document_type,
            "document_category": normalization_result.document_category,
            "report_date": normalization_result.report_date.isoformat() if normalization_result.report_date else None,
            "normalized_payload": normalization_result.normalized_payload,
            "measurements": normalization_result.measurements,
        }
        payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()
