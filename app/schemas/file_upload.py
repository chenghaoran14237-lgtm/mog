from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecordResponse(BaseModel):
    id: int
    user_id: int | None
    source: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordFileResponse(BaseModel):
    id: int
    record_id: int
    original_filename: str
    display_name: str | None
    content_type: str | None
    size_bytes: int
    storage_provider: str | None
    storage_key: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    record: RecordResponse
    file: RecordFileResponse
