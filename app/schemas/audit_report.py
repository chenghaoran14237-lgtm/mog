from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditReportCreateRequest(BaseModel):
    selected_document_version_ids: list[int] = Field(..., min_length=1)
    title: str | None = Field(default=None, max_length=255)
    max_iterations: int = Field(default=8, ge=2, le=20)


class AuditReportRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str | None
    status: str
    selected_document_version_ids: list[int]
    graph_state: dict
    final_report: dict | None
    iteration_count: int
    max_iterations: int
    stop_reason: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditReportEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    user_id: int
    sequence: int
    event_type: str
    node_name: str | None
    edge_source: str | None
    edge_target: str | None
    status: str | None
    message: str | None
    payload: dict
    created_at: datetime


class AuditReportNodeStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    user_id: int
    node_name: str
    status: str
    visit_count: int
    last_event_id: int | None
    output: dict
    updated_at: datetime


class AuditReportRunDetailResponse(BaseModel):
    run: AuditReportRunResponse
    events: list[AuditReportEventResponse]
    node_states: list[AuditReportNodeStateResponse]
