from datetime import datetime

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: int
    task_type: str
    resource_type: str
    resource_id: int
    status: str
    request_id: str | None
    attempt_count: int
    max_retries: int
    result_resource_type: str | None
    result_resource_id: int | None
    last_error_category: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_error_retryable: bool
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]


class TaskSubmissionResponse(BaseModel):
    task: TaskResponse
    created: bool


class TaskEventResponse(BaseModel):
    id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    request_id: str | None
    message: str | None
    payload: dict
    created_at: datetime


class TaskEventListResponse(BaseModel):
    items: list[TaskEventResponse]


class TaskResultResponse(BaseModel):
    task: TaskResponse
    result_type: str
    data: dict


class ProviderEventResponse(BaseModel):
    id: int
    provider_type: str
    provider_name: str
    operation: str
    resource_type: str
    resource_id: int
    status: str
    error_category: str | None
    error_code: str | None
    retryable: bool
    duration_ms: int | None
    request_id: str | None
    payload: dict
    created_at: datetime


class ProviderEventListResponse(BaseModel):
    items: list[ProviderEventResponse]


class ProviderEventSummaryItemResponse(BaseModel):
    provider_type: str
    provider_name: str
    status: str
    event_count: int
    avg_duration_ms: float | None
    last_event_at: datetime | None


class ProviderEventSummaryResponse(BaseModel):
    window_hours: int
    items: list[ProviderEventSummaryItemResponse]
