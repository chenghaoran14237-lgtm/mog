from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.document_version import DocumentVersion
from app.models.extracted_document import ExtractedDocument
from app.models.measurement import Measurement
from app.models.record import Record
from app.services.document_semantics import NARRATIVE_CONTEXT


@dataclass(slots=True)
class MeasurementListRow:
    measurement: Measurement
    record_id: int
    record_file_id: int
    document_type: str
    document_category: str
    document_display_name: str | None
    document_version_id: int | None
    version_number: int | None


class MeasurementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _effective_observed_at(self):
        return func.coalesce(Measurement.observed_at, Measurement.created_at)

    def list_measurements(
        self,
        *,
        user_id: int | None = None,
        record_id: int | None = None,
        record_file_id: int | None = None,
        extracted_document_id: int | None = None,
        document_version_id: int | None = None,
        name: str | None = None,
        current_only: bool = True,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[MeasurementListRow], int]:
        filters = self._build_filters(
            user_id=user_id,
            record_id=record_id,
            record_file_id=record_file_id,
            extracted_document_id=extracted_document_id,
            document_version_id=document_version_id,
            name=name,
            current_only=current_only,
        )
        sort_column = self._resolve_sort_column(sort_by)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        total_statement = (
            select(func.count(Measurement.id))
            .select_from(Measurement)
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(DocumentVersion, Measurement.document_version_id == DocumentVersion.id, isouter=True)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
        )
        total = self.session.scalar(total_statement) or 0

        offset = (page - 1) * page_size
        statement = (
            select(
                Measurement,
                ExtractedDocument.record_id,
                ExtractedDocument.record_file_id,
                ExtractedDocument.document_type,
                ExtractedDocument.document_category,
                ExtractedDocument.display_name,
                Measurement.document_version_id,
                DocumentVersion.version_number,
            )
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(DocumentVersion, Measurement.document_version_id == DocumentVersion.id, isouter=True)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
            .order_by(order_clause, Measurement.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = self.session.execute(statement).all()
        return [
            MeasurementListRow(
                measurement=row[0],
                record_id=row[1],
                record_file_id=row[2],
                document_type=row[3],
                document_category=row[4],
                document_display_name=row[5],
                document_version_id=row[6],
                version_number=row[7],
            )
            for row in rows
        ], total

    def _build_filters(
        self,
        *,
        user_id: int | None,
        record_id: int | None,
        record_file_id: int | None,
        extracted_document_id: int | None,
        document_version_id: int | None,
        name: str | None,
        current_only: bool,
    ) -> list[object]:
        filters: list[object] = []
        if user_id is not None:
            filters.append(Record.user_id == user_id)
        if record_id is not None:
            filters.append(ExtractedDocument.record_id == record_id)
        if record_file_id is not None:
            filters.append(ExtractedDocument.record_file_id == record_file_id)
        if extracted_document_id is not None:
            filters.append(Measurement.extracted_document_id == extracted_document_id)
        if document_version_id is not None:
            filters.append(Measurement.document_version_id == document_version_id)
        if name is not None:
            filters.append(Measurement.name == name)
        if current_only:
            filters.append(DocumentVersion.is_current.is_(True))
        filters.append(or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT))
        return filters

    def _resolve_sort_column(self, sort_by: str):
        sort_columns = {
            "created_at": self._effective_observed_at(),
            "observed_at": self._effective_observed_at(),
            "id": Measurement.id,
            "name": Measurement.name,
            "value_numeric": Measurement.value_numeric,
        }
        return sort_columns.get(sort_by, self._effective_observed_at())

    def search_by_name(
        self,
        *,
        user_id: int,
        name_pattern: str,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[MeasurementListRow], int]:
        """按指标名称搜索（支持模糊匹配）

        Args:
            user_id: 用户ID
            name_pattern: 指标名称模式（支持模糊匹配）
            start_date: 开始日期
            end_date: 结束日期
            page: 页码
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (测量数据列表, 总数)
        """
        filters = [Record.user_id == user_id]

        # 模糊搜索指标名称
        filters.append(Measurement.name.like(f"%{name_pattern}%"))

        # 日期范围过滤
        if start_date:
            filters.append(self._effective_observed_at() >= start_date)
        if end_date:
            filters.append(self._effective_observed_at() <= end_date)

        # 只查询当前版本
        filters.append(DocumentVersion.is_current.is_(True))
        filters.append(or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT))

        sort_column = self._resolve_sort_column(sort_by)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        # 计算总数
        total_statement = (
            select(func.count(Measurement.id))
            .select_from(Measurement)
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(DocumentVersion, Measurement.document_version_id == DocumentVersion.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
        )
        total = self.session.scalar(total_statement) or 0

        # 查询数据
        offset = (page - 1) * page_size
        statement = (
            select(
                Measurement,
                ExtractedDocument.record_id,
                ExtractedDocument.record_file_id,
                ExtractedDocument.document_type,
                ExtractedDocument.document_category,
                ExtractedDocument.display_name,
                Measurement.document_version_id,
                DocumentVersion.version_number,
            )
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(DocumentVersion, Measurement.document_version_id == DocumentVersion.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
            .order_by(order_clause, Measurement.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = self.session.execute(statement).all()

        return [
            MeasurementListRow(
                measurement=row[0],
                record_id=row[1],
                record_file_id=row[2],
                document_type=row[3],
                document_category=row[4],
                document_display_name=row[5],
                document_version_id=row[6],
                version_number=row[7],
            )
            for row in rows
        ], total

    def query_by_time_range(
        self,
        *,
        user_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        measurement_names: list[str] | None = None,
    ) -> list[Measurement]:
        """按时间范围和指标名称查询测量值"""
        filters = [Record.user_id == user_id]

        if start_date:
            filters.append(self._effective_observed_at() >= start_date)
        if end_date:
            filters.append(self._effective_observed_at() <= end_date)
        if measurement_names:
            filters.append(Measurement.name.in_(measurement_names))
        filters.append(or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT))

        statement = (
            select(Measurement)
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
            .order_by(self._effective_observed_at().asc())
        )

        return list(self.session.scalars(statement).all())

    def get_measurement_statistics(
        self,
        *,
        user_id: int,
        measurement_name: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """获取指标统计信息"""
        filters = [
            Record.user_id == user_id,
            Measurement.name == measurement_name,
            Measurement.value_numeric.isnot(None),
        ]

        if start_date:
            filters.append(self._effective_observed_at() >= start_date)
        if end_date:
            filters.append(self._effective_observed_at() <= end_date)
        filters.append(or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT))

        statement = (
            select(
                func.count(Measurement.id).label("count"),
                func.min(Measurement.value_numeric).label("min"),
                func.max(Measurement.value_numeric).label("max"),
                func.avg(Measurement.value_numeric).label("avg"),
            )
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
        )

        result = self.session.execute(statement).one()

        return {
            "count": result.count or 0,
            "min": float(result.min) if result.min is not None else None,
            "max": float(result.max) if result.max is not None else None,
            "avg": float(result.avg) if result.avg is not None else None,
        }

    def get_distinct_measurement_names(self, *, user_id: int) -> list[str]:
        """获取用户所有不同的测量指标名称"""
        statement = (
            select(Measurement.name)
            .distinct()
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(
                Record.user_id == user_id,
                or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT),
            )
            .order_by(Measurement.name.asc())
        )

        return list(self.session.scalars(statement).all())

    def get_measurements_by_ids(
        self,
        *,
        user_id: int,
        measurement_ids: list[int],
    ) -> list[MeasurementListRow]:
        """根据ID列表获取测量数据"""
        if not measurement_ids:
            return []

        statement = (
            select(
                Measurement,
                ExtractedDocument.record_id,
                ExtractedDocument.record_file_id,
                ExtractedDocument.document_type,
                ExtractedDocument.document_category,
                ExtractedDocument.display_name,
                Measurement.document_version_id,
                DocumentVersion.version_number,
            )
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(DocumentVersion, Measurement.document_version_id == DocumentVersion.id, isouter=True)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(
                Record.user_id == user_id,
                Measurement.id.in_(measurement_ids),
                or_(ExtractedDocument.document_category.is_(None), ExtractedDocument.document_category != NARRATIVE_CONTEXT),
            )
            .order_by(Measurement.id.asc())
        )
        rows = self.session.execute(statement).all()

        return [
            MeasurementListRow(
                measurement=row[0],
                record_id=row[1],
                record_file_id=row[2],
                document_type=row[3],
                document_category=row[4],
                document_display_name=row[5],
                document_version_id=row[6],
                version_number=row[7],
            )
            for row in rows
        ]
