from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.statuses import NormalizationStatus
from app.models.document_version import DocumentVersion
from app.models.extracted_document import ExtractedDocument
from app.models.measurement import Measurement
from app.models.record import Record
from app.models.record_file import RecordFile


@dataclass(slots=True)
class ExtractedDocumentListRow:
    document: ExtractedDocument
    current_version: DocumentVersion | None
    measurement_count: int
    uploaded_at: datetime | None


class ExtractedDocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, document_id: int, user_id: int | None = None) -> ExtractedDocument | None:
        statement = (
            select(ExtractedDocument)
            .options(selectinload(ExtractedDocument.versions).selectinload(DocumentVersion.measurements))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(ExtractedDocument.id == document_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_by_ocr_result_id(self, ocr_result_id: int, user_id: int | None = None) -> ExtractedDocument | None:
        statement = (
            select(ExtractedDocument)
            .options(selectinload(ExtractedDocument.versions).selectinload(DocumentVersion.measurements))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(ExtractedDocument.ocr_result_id == ocr_result_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_by_record_file_id(self, record_file_id: int, user_id: int | None = None) -> ExtractedDocument | None:
        statement = (
            select(ExtractedDocument)
            .options(selectinload(ExtractedDocument.versions).selectinload(DocumentVersion.measurements))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(ExtractedDocument.record_file_id == record_file_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_or_create_document(
        self,
        *,
        ocr_result_id: int,
        record_id: int,
        record_file_id: int,
        document_type: str,
        display_name: str | None = None,
    ) -> ExtractedDocument:
        existing = self.get_by_record_file_id(record_file_id)
        if existing is not None:
            return existing
        document = ExtractedDocument(
            ocr_result_id=ocr_result_id,
            current_ocr_result_id=ocr_result_id,
            record_id=record_id,
            record_file_id=record_file_id,
            document_type=document_type,
            document_category="narrative_context",
            display_name=display_name,
            status=NormalizationStatus.PROCESSING,
            report_date=None,
            normalized_payload={},
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def update_projection(
        self,
        document_id: int,
        *,
        status: str,
        normalized_payload: dict,
        document_type: str | None = None,
        document_category: str | None = None,
        report_date=None,
        current_ocr_result_id: int | None = None,
    ) -> ExtractedDocument:
        document = self.session.get(ExtractedDocument, document_id)
        if document is None:
            raise ValueError("Extracted document not found")
        document.status = status
        document.normalized_payload = normalized_payload
        if document_type is not None:
            document.document_type = document_type
        if document_category is not None:
            document.document_category = document_category
        if report_date is not None:
            document.report_date = report_date
        if current_ocr_result_id is not None:
            document.current_ocr_result_id = current_ocr_result_id
        self.session.commit()
        self.session.refresh(document)
        return document

    def list_documents(
        self,
        *,
        user_id: int | None = None,
        record_id: int | None = None,
        record_file_id: int | None = None,
        document_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[ExtractedDocumentListRow], int]:
        current_version_alias = DocumentVersion
        filters = self._build_filters(
            user_id=user_id,
            record_id=record_id,
            record_file_id=record_file_id,
            document_type=document_type,
            status=status,
        )
        measurement_count_subquery = (
            select(func.count(Measurement.id))
            .where(Measurement.document_version_id == current_version_alias.id)
            .correlate(current_version_alias)
            .scalar_subquery()
        )
        total_statement = (
            select(func.count(ExtractedDocument.id))
            .select_from(ExtractedDocument)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .join(RecordFile, ExtractedDocument.record_file_id == RecordFile.id)
            .join(
                current_version_alias,
                (current_version_alias.document_id == ExtractedDocument.id) & (current_version_alias.is_current.is_(True)),
                isouter=True,
            )
            .where(*filters)
        )
        total = self.session.scalar(total_statement) or 0

        sort_column = self._resolve_sort_column(sort_by)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        offset = (page - 1) * page_size
        statement = (
            select(ExtractedDocument, current_version_alias, measurement_count_subquery.label("measurement_count"), RecordFile.created_at)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .join(RecordFile, ExtractedDocument.record_file_id == RecordFile.id)
            .join(
                current_version_alias,
                (current_version_alias.document_id == ExtractedDocument.id) & (current_version_alias.is_current.is_(True)),
                isouter=True,
            )
            .where(*filters)
            .order_by(order_clause, ExtractedDocument.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = self.session.execute(statement).all()
        return [
            ExtractedDocumentListRow(document=row[0], current_version=row[1], measurement_count=row[2] or 0, uploaded_at=row[3])
            for row in rows
        ], total

    def get_current_version(self, document_id: int, *, user_id: int | None = None) -> DocumentVersion | None:
        document = self.get_by_id(document_id, user_id=user_id)
        if document is None:
            return None
        versions = [row for row in document.versions if row.is_current]
        if not versions:
            return None
        versions.sort(key=lambda row: row.id, reverse=True)
        return versions[0]

    def list_versions(self, document_id: int) -> list[DocumentVersion]:
        statement = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.measurements))
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc(), DocumentVersion.id.desc())
        )
        return list(self.session.scalars(statement).all())

    def _build_filters(
        self,
        *,
        user_id: int | None,
        record_id: int | None,
        record_file_id: int | None,
        document_type: str | None,
        status: str | None,
    ) -> list[object]:
        filters: list[object] = []
        if user_id is not None:
            filters.append(Record.user_id == user_id)
        if record_id is not None:
            filters.append(ExtractedDocument.record_id == record_id)
        if record_file_id is not None:
            filters.append(ExtractedDocument.record_file_id == record_file_id)
        if document_type is not None:
            filters.append(ExtractedDocument.document_type == document_type)
        if status is not None:
            filters.append(ExtractedDocument.status == status)
        return filters

    def _resolve_sort_column(self, sort_by: str):
        sort_columns = {
            "created_at": RecordFile.created_at,
            "id": ExtractedDocument.id,
            "document_type": ExtractedDocument.document_type,
            "report_date": ExtractedDocument.report_date,
        }
        return sort_columns.get(sort_by, RecordFile.created_at)

    def delete(self, document_id: int) -> None:
        """删除文档（级联删除相关数据）"""
        document = self.session.get(ExtractedDocument, document_id)
        if document:
            self.session.delete(document)
            self.session.commit()
