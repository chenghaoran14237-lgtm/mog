import math

from fastapi import HTTPException, status

from app.core.errors import APIError
from app.repositories.document_version_repository import DocumentVersionListRow, DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentListRow, ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementListRow, MeasurementRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.ingestion import MeasurementResponse
from app.schemas.query import (
    DocumentVersionDiffResponse,
    DocumentVersionDetailResponse,
    DocumentVersionListResponse,
    DocumentVersionMeasurementDeltaResponse,
    DocumentVersionSummaryResponse,
    ExtractedDocumentDetailResponse,
    ExtractedDocumentListResponse,
    ExtractedDocumentSummaryResponse,
    MeasurementListResponse,
    MeasurementQueryResponse,
    PaginationResponse,
)
from app.services.document_semantics import category_capabilities


class QueryService:
    def __init__(
        self,
        record_repository: RecordRepository,
        extracted_document_repository: ExtractedDocumentRepository,
        document_version_repository: DocumentVersionRepository,
        measurement_repository: MeasurementRepository,
    ) -> None:
        self.record_repository = record_repository
        self.extracted_document_repository = extracted_document_repository
        self.document_version_repository = document_version_repository
        self.measurement_repository = measurement_repository

    def list_documents(
        self,
        *,
        current_user_id: int,
        record_id: int | None = None,
        record_file_id: int | None = None,
        document_type: str | None = None,
        status_value: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ExtractedDocumentListResponse:
        rows, total = self.extracted_document_repository.list_documents(
            user_id=current_user_id,
            record_id=record_id,
            record_file_id=record_file_id,
            document_type=document_type,
            status=status_value,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return ExtractedDocumentListResponse(
            items=[self._build_document_summary(row) for row in rows],
            pagination=self._build_pagination(page=page, page_size=page_size, total_items=total, sort_by=sort_by, sort_order=sort_order),
        )

    def get_document(self, document_id: int, current_user_id: int) -> ExtractedDocumentDetailResponse:
        document = self.extracted_document_repository.get_by_id(document_id, user_id=current_user_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted document not found")
        record_file = self.record_repository.get_record_file_by_id(document.record_file_id, user_id=current_user_id)
        version = self.document_version_repository.get_current_for_document(document_id, user_id=current_user_id)
        measurements = [] if version is None else [MeasurementResponse.model_validate(row) for row in sorted(version.measurements, key=lambda item: item.id)]
        capabilities = category_capabilities(document.document_category)
        uploaded_at = record_file.created_at if record_file is not None else document.created_at
        return ExtractedDocumentDetailResponse(
            id=document.id,
            ocr_result_id=document.ocr_result_id,
            current_ocr_result_id=document.current_ocr_result_id,
            record_id=document.record_id,
            record_file_id=document.record_file_id,
            document_type=document.document_type,
            document_category=document.document_category,
            display_name=document.display_name,
            current_version_id=version.id if version is not None else None,
            current_version_number=version.version_number if version is not None else None,
            measurement_count=len(measurements),
            normalized_payload=version.normalized_payload if version is not None else {},
            report_date=version.report_date if version is not None else document.report_date,
            uploaded_at=uploaded_at,
            supports_measurements=capabilities["supports_measurements"],
            supports_trend_analysis=capabilities["supports_trend_analysis"],
            supports_llm_context=capabilities["supports_llm_context"],
            created_at=uploaded_at,
            measurements=measurements,
        )

    def list_documents_for_record(self, record_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "created_at", sort_order: str = "desc") -> ExtractedDocumentListResponse:
        self._ensure_record_exists(record_id, current_user_id)
        return self.list_documents(current_user_id=current_user_id, record_id=record_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

    def list_documents_for_file(self, record_file_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "created_at", sort_order: str = "desc") -> ExtractedDocumentListResponse:
        self._ensure_record_file_exists(record_file_id, current_user_id)
        return self.list_documents(current_user_id=current_user_id, record_file_id=record_file_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

    def list_document_versions(self, document_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "version_number", sort_order: str = "desc") -> DocumentVersionListResponse:
        document = self.extracted_document_repository.get_by_id(document_id, user_id=current_user_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted document not found")
        rows, total = self.document_version_repository.list_versions(
            document_id=document_id,
            user_id=current_user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return DocumentVersionListResponse(
            items=[self._build_document_version_summary(row) for row in rows],
            pagination=self._build_pagination(page=page, page_size=page_size, total_items=total, sort_by=sort_by, sort_order=sort_order),
        )

    def get_current_document_version(self, document_id: int, *, current_user_id: int) -> DocumentVersionDetailResponse:
        version = self.document_version_repository.get_current_for_document(document_id, user_id=current_user_id)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
        return self._build_document_version_detail(version)

    def get_document_version(self, version_id: int, *, current_user_id: int) -> DocumentVersionDetailResponse:
        version = self.document_version_repository.get_by_id(version_id, user_id=current_user_id)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
        return self._build_document_version_detail(version)

    def compare_document_versions(self, from_version_id: int, to_version_id: int, *, current_user_id: int) -> DocumentVersionDiffResponse:
        from_version = self.document_version_repository.get_by_id(from_version_id, user_id=current_user_id)
        to_version = self.document_version_repository.get_by_id(to_version_id, user_id=current_user_id)
        if from_version is None or to_version is None:
            raise APIError(status_code=404, code="document_version_not_found", message="Document version not found")
        if from_version.document_id != to_version.document_id:
            raise APIError(status_code=409, code="document_version_compare_scope_mismatch", message="Document versions must belong to the same document")

        from_measurements = {row.name: row for row in from_version.measurements}
        to_measurements = {row.name: row for row in to_version.measurements}
        all_names = sorted(set(from_measurements) | set(to_measurements))

        added_measurements: list[str] = []
        removed_measurements: list[str] = []
        changed_measurements: list[DocumentVersionMeasurementDeltaResponse] = []
        for name in all_names:
            from_row = from_measurements.get(name)
            to_row = to_measurements.get(name)
            if from_row is None and to_row is not None:
                added_measurements.append(name)
                continue
            if from_row is not None and to_row is None:
                removed_measurements.append(name)
                continue
            if from_row is not None and to_row is not None:
                if (
                    from_row.value_text != to_row.value_text
                    or from_row.value_numeric != to_row.value_numeric
                    or from_row.unit != to_row.unit
                ):
                    changed_measurements.append(
                        DocumentVersionMeasurementDeltaResponse(
                            name=name,
                            from_value_text=from_row.value_text,
                            to_value_text=to_row.value_text,
                            from_value_numeric=from_row.value_numeric,
                            to_value_numeric=to_row.value_numeric,
                            unit=to_row.unit or from_row.unit,
                        )
                    )

        from_payload_keys = set(from_version.normalized_payload.keys())
        to_payload_keys = set(to_version.normalized_payload.keys())
        changed_payload_keys = sorted(
            key for key in (from_payload_keys & to_payload_keys)
            if from_version.normalized_payload.get(key) != to_version.normalized_payload.get(key)
        )

        return DocumentVersionDiffResponse(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            from_version_number=from_version.version_number,
            to_version_number=to_version.version_number,
            from_ocr_result_id=from_version.created_from_ocr_result_id,
            to_ocr_result_id=to_version.created_from_ocr_result_id,
            snapshot_changed=from_version.snapshot_hash != to_version.snapshot_hash,
            measurement_count_delta=len(to_version.measurements) - len(from_version.measurements),
            added_measurements=added_measurements,
            removed_measurements=removed_measurements,
            changed_measurements=changed_measurements,
            added_payload_keys=sorted(to_payload_keys - from_payload_keys),
            removed_payload_keys=sorted(from_payload_keys - to_payload_keys),
            changed_payload_keys=changed_payload_keys,
        )

    def list_measurements(
        self,
        *,
        current_user_id: int,
        record_id: int | None = None,
        record_file_id: int | None = None,
        document_id: int | None = None,
        document_version_id: int | None = None,
        name: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        current_only: bool = True,
    ) -> MeasurementListResponse:
        rows, total = self.measurement_repository.list_measurements(
            user_id=current_user_id,
            record_id=record_id,
            record_file_id=record_file_id,
            extracted_document_id=document_id,
            document_version_id=document_version_id,
            name=name,
            current_only=current_only,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return MeasurementListResponse(
            items=[self._build_measurement_item(row) for row in rows],
            pagination=self._build_pagination(page=page, page_size=page_size, total_items=total, sort_by=sort_by, sort_order=sort_order),
        )

    def list_measurements_for_record(self, record_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "created_at", sort_order: str = "desc") -> MeasurementListResponse:
        self._ensure_record_exists(record_id, current_user_id)
        return self.list_measurements(current_user_id=current_user_id, record_id=record_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

    def list_measurements_for_file(self, record_file_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "created_at", sort_order: str = "desc") -> MeasurementListResponse:
        self._ensure_record_file_exists(record_file_id, current_user_id)
        return self.list_measurements(current_user_id=current_user_id, record_file_id=record_file_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

    def list_measurements_for_document(self, document_id: int, *, current_user_id: int, page: int = 1, page_size: int = 20, sort_by: str = "created_at", sort_order: str = "desc") -> MeasurementListResponse:
        document = self.extracted_document_repository.get_by_id(document_id, user_id=current_user_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted document not found")
        return self.list_measurements(current_user_id=current_user_id, document_id=document_id, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

    def search_measurements_by_name(
        self,
        *,
        current_user_id: int,
        name_pattern: str,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> MeasurementListResponse:
        """按指标名称搜索测量数据（支持模糊搜索）

        Args:
            current_user_id: 用户ID
            name_pattern: 指标名称（支持模糊匹配）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            page: 页码
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            测量数据列表
        """
        rows, total = self.measurement_repository.search_by_name(
            user_id=current_user_id,
            name_pattern=name_pattern,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return MeasurementListResponse(
            items=[self._build_measurement_item(row) for row in rows],
            pagination=self._build_pagination(page=page, page_size=page_size, total_items=total, sort_by=sort_by, sort_order=sort_order),
        )

    def _ensure_record_exists(self, record_id: int, current_user_id: int) -> None:
        record = self.record_repository.get_record_by_id(record_id, user_id=current_user_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    def _ensure_record_file_exists(self, record_file_id: int, current_user_id: int) -> None:
        record_file = self.record_repository.get_record_file_by_id(record_file_id, user_id=current_user_id)
        if record_file is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record file not found")

    def _build_document_summary(self, row: ExtractedDocumentListRow) -> ExtractedDocumentSummaryResponse:
        version = row.current_version
        capabilities = category_capabilities(row.document.document_category)
        uploaded_at = row.uploaded_at or row.document.created_at
        return ExtractedDocumentSummaryResponse(
            id=row.document.id,
            ocr_result_id=row.document.ocr_result_id,
            current_ocr_result_id=row.document.current_ocr_result_id,
            record_id=row.document.record_id,
            record_file_id=row.document.record_file_id,
            document_type=row.document.document_type,
            document_category=row.document.document_category,
            display_name=row.document.display_name,
            current_version_id=version.id if version is not None else None,
            current_version_number=version.version_number if version is not None else None,
            measurement_count=row.measurement_count,
            report_date=version.report_date if version is not None else row.document.report_date,
            uploaded_at=uploaded_at,
            supports_measurements=capabilities["supports_measurements"],
            supports_trend_analysis=capabilities["supports_trend_analysis"],
            supports_llm_context=capabilities["supports_llm_context"],
            created_at=uploaded_at,
        )

    def _build_document_version_summary(self, row: DocumentVersionListRow) -> DocumentVersionSummaryResponse:
        return DocumentVersionSummaryResponse(
            id=row.version.id,
            document_id=row.version.document_id,
            version_number=row.version.version_number,
            supersedes_version_id=row.version.supersedes_version_id,
            is_current=row.version.is_current,
            created_from_ocr_result_id=row.version.created_from_ocr_result_id,
            measurement_count=row.measurement_count,
            report_date=row.version.report_date,
            created_at=row.version.created_at,
        )

    def _build_document_version_detail(self, version) -> DocumentVersionDetailResponse:
        measurements = [MeasurementResponse.model_validate(row) for row in sorted(version.measurements, key=lambda item: item.id)]
        return DocumentVersionDetailResponse(
            id=version.id,
            document_id=version.document_id,
            version_number=version.version_number,
            supersedes_version_id=version.supersedes_version_id,
            is_current=version.is_current,
            created_from_ocr_result_id=version.created_from_ocr_result_id,
            snapshot_hash=version.snapshot_hash,
            normalized_payload=version.normalized_payload,
            measurement_count=len(measurements),
            report_date=version.report_date,
            created_at=version.created_at,
            measurements=measurements,
        )

    def _build_measurement_item(self, row: MeasurementListRow) -> MeasurementQueryResponse:
        measurement = row.measurement
        return MeasurementQueryResponse(
            id=measurement.id,
            document_id=measurement.extracted_document_id,
            document_version_id=row.document_version_id,
            document_version_number=row.version_number,
            record_id=row.record_id,
            record_file_id=row.record_file_id,
            document_type=row.document_type,
            document_category=row.document_category,
            document_display_name=row.document_display_name,
            name=measurement.name,
            value_text=measurement.value_text,
            value_numeric=measurement.value_numeric,
            unit=measurement.unit,
            observed_at=measurement.observed_at,
            created_at=measurement.observed_at or measurement.created_at,
        )

    def delete_document(self, document_id: int, current_user_id: int) -> None:
        """删除文档"""
        # 验证文档存在且用户有权限（通过user_id过滤）
        document = self.extracted_document_repository.get_by_id(document_id, user_id=current_user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # 删除文档（级联删除会处理相关数据）
        self.extracted_document_repository.delete(document_id)

    def rename_document(self, document_id: int, new_name: str, current_user_id: int) -> None:
        """重命名文档（设置显示名称）"""
        # 验证文档存在且用户有权限
        document = self.extracted_document_repository.get_by_id(document_id, user_id=current_user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # 更新显示名称
        document.display_name = new_name.strip()
        self.extracted_document_repository.session.commit()

    def get_measurement_timeseries(
        self,
        *,
        current_user_id: int,
        name_pattern: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """获取指标的时序数据（用于绘图）"""
        # 获取所有匹配的测量数据
        rows, _ = self.measurement_repository.search_by_name(
            user_id=current_user_id,
            name_pattern=name_pattern,
            start_date=start_date,
            end_date=end_date,
            page=1,
            page_size=1000,  # 获取足够多的数据点
            sort_by="created_at",
            sort_order="asc",
        )

        if not rows:
            return {
                "name": name_pattern,
                "unit": None,
                "data_points": []
            }

        # 提取数据点
        data_points = []
        unit = None
        name = None

        for row in rows:
            measurement = row.measurement
            if unit is None:
                unit = measurement.unit
            if name is None:
                name = measurement.name
            effective_date = measurement.observed_at or measurement.created_at

            data_points.append({
                "date": effective_date.strftime("%Y-%m-%d %H:%M:%S"),
                "value": measurement.value_numeric,
                "value_text": measurement.value_text,
                "document_id": measurement.extracted_document_id,
            })

        return {
            "name": name or name_pattern,
            "unit": unit,
            "data_points": data_points,
            "total_points": len(data_points)
        }

    def _build_pagination(self, *, page: int, page_size: int, total_items: int, sort_by: str, sort_order: str) -> PaginationResponse:
        total_pages = math.ceil(total_items / page_size) if total_items else 0
        return PaginationResponse(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages, sort_by=sort_by, sort_order=sort_order)
