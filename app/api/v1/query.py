from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
from app.models.user import User
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.query import (
    DocumentVersionDiffResponse,
    DocumentVersionDetailResponse,
    DocumentVersionListResponse,
    ExtractedDocumentDetailResponse,
    ExtractedDocumentListResponse,
    MeasurementListResponse,
    QuerySelectionRequest,
    QuerySelectionResponse,
)
from app.services.query_service import QueryService

router = APIRouter()


def build_query_service(session: Session) -> QueryService:
    return QueryService(
        record_repository=RecordRepository(session),
        extracted_document_repository=ExtractedDocumentRepository(session),
        document_version_repository=DocumentVersionRepository(session),
        measurement_repository=MeasurementRepository(session),
    )


@router.get("/documents", response_model=ExtractedDocumentListResponse)
def list_documents(
    record_id: int | None = Query(default=None, ge=1),
    file_id: int | None = Query(default=None, ge=1),
    document_type: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "id", "document_type", "report_date"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ExtractedDocumentListResponse:
    service = build_query_service(session)
    return service.list_documents(
        current_user_id=current_user.id,
        record_id=record_id,
        record_file_id=file_id,
        document_type=document_type,
        status_value=status_value,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/documents/{document_id}", response_model=ExtractedDocumentDetailResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ExtractedDocumentDetailResponse:
    service = build_query_service(session)
    return service.get_document(document_id, current_user_id=current_user.id)


@router.get("/documents/{document_id}/versions", response_model=DocumentVersionListResponse)
def list_document_versions(
    document_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "id", "version_number"] = "version_number",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> DocumentVersionListResponse:
    service = build_query_service(session)
    return service.list_document_versions(
        document_id=document_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/documents/{document_id}/versions/current", response_model=DocumentVersionDetailResponse)
def get_current_document_version(
    document_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> DocumentVersionDetailResponse:
    service = build_query_service(session)
    return service.get_current_document_version(document_id, current_user_id=current_user.id)


@router.get("/document-versions/compare", response_model=DocumentVersionDiffResponse)
def compare_document_versions(
    from_id: int = Query(..., ge=1),
    to_id: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> DocumentVersionDiffResponse:
    service = build_query_service(session)
    return service.compare_document_versions(from_id, to_id, current_user_id=current_user.id)


@router.get("/document-versions/{version_id}", response_model=DocumentVersionDetailResponse)
def get_document_version(
    version_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> DocumentVersionDetailResponse:
    service = build_query_service(session)
    return service.get_document_version(version_id, current_user_id=current_user.id)


@router.get("/records/{record_id}/documents", response_model=ExtractedDocumentListResponse)
def list_documents_for_record(
    record_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "id", "document_type", "report_date"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ExtractedDocumentListResponse:
    service = build_query_service(session)
    return service.list_documents_for_record(
        record_id=record_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/files/{file_id}/documents", response_model=ExtractedDocumentListResponse)
def list_documents_for_file(
    file_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "id", "document_type", "report_date"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> ExtractedDocumentListResponse:
    service = build_query_service(session)
    return service.list_documents_for_file(
        record_file_id=file_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/measurements", response_model=MeasurementListResponse)
def list_measurements(
    record_id: int | None = Query(default=None, ge=1),
    file_id: int | None = Query(default=None, ge=1),
    document_id: int | None = Query(default=None, ge=1),
    document_version_id: int | None = Query(default=None, ge=1),
    name: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "observed_at", "id", "name", "value_numeric"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> MeasurementListResponse:
    service = build_query_service(session)
    return service.list_measurements(
        current_user_id=current_user.id,
        record_id=record_id,
        record_file_id=file_id,
        document_id=document_id,
        document_version_id=document_version_id,
        name=name,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/records/{record_id}/measurements", response_model=MeasurementListResponse)
def list_measurements_for_record(
    record_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "observed_at", "id", "name", "value_numeric"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> MeasurementListResponse:
    service = build_query_service(session)
    return service.list_measurements_for_record(
        record_id=record_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/files/{file_id}/measurements", response_model=MeasurementListResponse)
def list_measurements_for_file(
    file_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "observed_at", "id", "name", "value_numeric"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> MeasurementListResponse:
    service = build_query_service(session)
    return service.list_measurements_for_file(
        record_file_id=file_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/documents/{document_id}/measurements", response_model=MeasurementListResponse)
def list_measurements_for_document(
    document_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "observed_at", "id", "name", "value_numeric"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> MeasurementListResponse:
    service = build_query_service(session)
    return service.list_measurements_for_document(
        document_id=document_id,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/measurements/search", response_model=MeasurementListResponse)
def search_measurements(
    name: str = Query(..., description="测量指标名称（支持模糊搜索）"),
    start_date: str | None = Query(default=None, description="开始日期（YYYY-MM-DD）"),
    end_date: str | None = Query(default=None, description="结束日期（YYYY-MM-DD）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "observed_at", "id", "name", "value_numeric"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> MeasurementListResponse:
    service = build_query_service(session)
    return service.search_measurements_by_name(
        current_user_id=current_user.id,
        name_pattern=name,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/query/selections", response_model=QuerySelectionResponse)
def select_document_versions(
    payload: QuerySelectionRequest,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
) -> QuerySelectionResponse:
    from app.modules.query_api import QueryModuleAPI

    api = QueryModuleAPI.from_session(session)
    return api.select_document_versions(
        current_user_id=current_user.id,
        document_version_ids=payload.document_version_ids,
        requested_measurements=payload.requested_measurements,
    )


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
):
    """删除文档"""
    service = build_query_service(session)
    service.delete_document(document_id, current_user_id=current_user.id)
    return {"success": True, "message": "Document deleted successfully"}


@router.patch("/documents/{document_id}/rename")
def rename_document(
    document_id: int,
    new_name: str,
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
):
    """重命名文档（修改关联文件的原始文件名）"""
    service = build_query_service(session)
    service.rename_document(document_id, new_name, current_user_id=current_user.id)
    return {"success": True, "message": "Document renamed successfully", "new_name": new_name}


@router.get("/measurements/timeseries")
def get_measurement_timeseries(
    name: str = Query(..., description="测量指标名称（支持模糊搜索）"),
    start_date: str | None = Query(default=None, description="开始日期（YYYY-MM-DD）"),
    end_date: str | None = Query(default=None, description="结束日期（YYYY-MM-DD）"),
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
):
    """获取指标的时序数据（用于绘图）"""
    service = build_query_service(session)
    return service.get_measurement_timeseries(
        current_user_id=current_user.id,
        name_pattern=name,
        start_date=start_date,
        end_date=end_date,
    )
