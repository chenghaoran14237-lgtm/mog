from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeasurementResponse(BaseModel):
    id: int
    extracted_document_id: int
    document_version_id: int | None
    name: str
    value_text: str
    value_numeric: float | None
    unit: str | None
    observed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedDocumentResponse(BaseModel):
    id: int
    ocr_result_id: int
    record_id: int
    record_file_id: int
    document_type: str
    document_category: str
    status: str
    report_date: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    supersedes_version_id: int | None
    is_current: bool
    created_from_ocr_result_id: int
    snapshot_hash: str
    report_date: datetime | None = None
    normalized_payload: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NormalizeOCRResponse(BaseModel):
    document: ExtractedDocumentResponse
    version: DocumentVersionResponse
    measurements: list[MeasurementResponse]
    version_created: bool
