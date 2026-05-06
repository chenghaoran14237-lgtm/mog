from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.query import PaginationResponse


class OCRResultResponse(BaseModel):
    id: int
    record_file_id: int
    revision_number: int
    supersedes_ocr_result_id: int | None
    is_current: bool
    provider_name: str
    status: str
    raw_text: str
    raw_payload: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OCRResultListResponse(BaseModel):
    items: list[OCRResultResponse]
    pagination: PaginationResponse


class OCRRevisionDiffResponse(BaseModel):
    from_ocr_result_id: int
    to_ocr_result_id: int
    from_revision_number: int
    to_revision_number: int
    provider_changed: bool
    status_changed: bool
    raw_text_changed: bool
    raw_text_length_delta: int
    line_count_delta: int
    added_lines: list[str]
    removed_lines: list[str]
