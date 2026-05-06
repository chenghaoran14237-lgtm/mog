from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.document_version import DocumentVersion
from app.models.extracted_document import ExtractedDocument
from app.models.measurement import Measurement
from app.models.record import Record
from app.services.document_semantics import parse_datetime_value


@dataclass(slots=True)
class DocumentVersionListRow:
    version: DocumentVersion
    measurement_count: int
    document_type: str
    record_id: int
    record_file_id: int


class DocumentVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, version_id: int, *, user_id: int | None = None) -> DocumentVersion | None:
        statement = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.measurements))
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(DocumentVersion.id == version_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_current_for_document(self, document_id: int, *, user_id: int | None = None) -> DocumentVersion | None:
        statement = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.measurements))
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(DocumentVersion.document_id == document_id)
            .where(DocumentVersion.is_current.is_(True))
            .order_by(DocumentVersion.id.desc())
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def list_versions(
        self,
        *,
        document_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "version_number",
        sort_order: str = "desc",
    ) -> tuple[list[DocumentVersionListRow], int]:
        filters = [DocumentVersion.document_id == document_id, Record.user_id == user_id]
        measurement_count_subquery = (
            select(func.count(Measurement.id))
            .where(Measurement.document_version_id == DocumentVersion.id)
            .correlate(DocumentVersion)
            .scalar_subquery()
        )
        total_statement = (
            select(func.count(DocumentVersion.id))
            .select_from(DocumentVersion)
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
        )
        total = self.session.scalar(total_statement) or 0

        sort_column = self._resolve_sort_column(sort_by)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        offset = (page - 1) * page_size
        statement = (
            select(
                DocumentVersion,
                measurement_count_subquery.label("measurement_count"),
                ExtractedDocument.document_type,
                ExtractedDocument.record_id,
                ExtractedDocument.record_file_id,
            )
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(*filters)
            .order_by(order_clause, DocumentVersion.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = self.session.execute(statement).all()
        return [
            DocumentVersionListRow(
                version=row[0],
                measurement_count=row[1],
                document_type=row[2],
                record_id=row[3],
                record_file_id=row[4],
            )
            for row in rows
        ], total

    def create_version(
        self,
        *,
        document_id: int,
        created_from_ocr_result_id: int,
        snapshot_hash: str,
        report_date: datetime | None,
        normalized_payload: dict,
        measurements: list[dict],
    ) -> tuple[DocumentVersion, list[Measurement]]:
        current = self.get_current_for_document(document_id)
        next_version_number = 1 if current is None else current.version_number + 1
        if current is not None:
            current.is_current = False

        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version_number,
            supersedes_version_id=current.id if current is not None else None,
            is_current=True,
            created_from_ocr_result_id=created_from_ocr_result_id,
            snapshot_hash=snapshot_hash,
            report_date=report_date,
            normalized_payload=normalized_payload,
        )
        self.session.add(version)
        self.session.flush()

        document = self.session.get(ExtractedDocument, document_id)
        if document is None:
            raise ValueError("Extracted document not found")

        measurement_rows: list[Measurement] = []
        for item in measurements:
            observed_at = parse_datetime_value(item.get("observed_at")) or report_date
            row = Measurement(
                extracted_document_id=document_id,
                document_version_id=version.id,
                name=item["name"],
                value_text=item["value_text"],
                value_numeric=item.get("value_numeric"),
                unit=item.get("unit"),
                observed_at=observed_at,
            )
            self.session.add(row)
            measurement_rows.append(row)

        self.session.commit()
        return self.get_by_id(version.id), measurement_rows  # type: ignore[return-value]

    def _resolve_sort_column(self, sort_by: str):
        sort_columns = {
            "created_at": DocumentVersion.created_at,
            "id": DocumentVersion.id,
            "version_number": DocumentVersion.version_number,
        }
        return sort_columns.get(sort_by, DocumentVersion.version_number)
