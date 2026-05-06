from datetime import datetime

from pydantic import BaseModel

from app.schemas.ingestion import MeasurementResponse


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    sort_by: str
    sort_order: str


class ExtractedDocumentSummaryResponse(BaseModel):
    id: int
    ocr_result_id: int
    current_ocr_result_id: int | None
    record_id: int
    record_file_id: int
    document_type: str
    document_category: str
    display_name: str | None
    current_version_id: int | None
    current_version_number: int | None
    measurement_count: int
    report_date: datetime | None = None
    uploaded_at: datetime | None = None
    supports_measurements: bool
    supports_trend_analysis: bool
    supports_llm_context: bool
    created_at: datetime


class ExtractedDocumentDetailResponse(BaseModel):
    id: int
    ocr_result_id: int
    current_ocr_result_id: int | None
    record_id: int
    record_file_id: int
    document_type: str
    document_category: str
    display_name: str | None
    current_version_id: int | None
    current_version_number: int | None
    measurement_count: int
    normalized_payload: dict
    report_date: datetime | None = None
    uploaded_at: datetime | None = None
    supports_measurements: bool
    supports_trend_analysis: bool
    supports_llm_context: bool
    created_at: datetime
    measurements: list[MeasurementResponse]


class ExtractedDocumentListResponse(BaseModel):
    items: list[ExtractedDocumentSummaryResponse]
    pagination: PaginationResponse


class MeasurementQueryResponse(BaseModel):
    id: int
    document_id: int
    document_version_id: int | None
    document_version_number: int | None
    record_id: int
    record_file_id: int
    document_type: str
    document_category: str
    document_display_name: str | None
    name: str
    value_text: str
    value_numeric: float | None
    unit: str | None
    observed_at: datetime | None = None
    created_at: datetime


class MeasurementListResponse(BaseModel):
    items: list[MeasurementQueryResponse]
    pagination: PaginationResponse


class DocumentVersionSummaryResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    supersedes_version_id: int | None
    is_current: bool
    created_from_ocr_result_id: int
    measurement_count: int
    report_date: datetime | None = None
    created_at: datetime


class DocumentVersionDetailResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    supersedes_version_id: int | None
    is_current: bool
    created_from_ocr_result_id: int
    snapshot_hash: str
    normalized_payload: dict
    measurement_count: int
    report_date: datetime | None = None
    created_at: datetime
    measurements: list[MeasurementResponse]


class DocumentVersionListResponse(BaseModel):
    items: list[DocumentVersionSummaryResponse]
    pagination: PaginationResponse


class DocumentVersionMeasurementDeltaResponse(BaseModel):
    name: str
    from_value_text: str | None
    to_value_text: str | None
    from_value_numeric: float | None
    to_value_numeric: float | None
    unit: str | None


class DocumentVersionDiffResponse(BaseModel):
    from_version_id: int
    to_version_id: int
    from_version_number: int
    to_version_number: int
    from_ocr_result_id: int
    to_ocr_result_id: int
    snapshot_changed: bool
    measurement_count_delta: int
    added_measurements: list[str]
    removed_measurements: list[str]
    changed_measurements: list[DocumentVersionMeasurementDeltaResponse]
    added_payload_keys: list[str]
    removed_payload_keys: list[str]
    changed_payload_keys: list[str]


class QuerySelectionRequest(BaseModel):
    document_version_ids: list[int]
    requested_measurements: list[str] = []


class QuerySelectionDocumentVersion(BaseModel):
    version: DocumentVersionDetailResponse
    selected_measurements: list[MeasurementResponse]


class QuerySelectionResponse(BaseModel):
    selected_document_version_ids: list[int]
    selected_versions: list[QuerySelectionDocumentVersion]
    selected_measurements: list[MeasurementResponse]
    source_count: int
