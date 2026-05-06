from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.statuses import OCRStatus
from app.models.ocr_result import OCRResult
from app.models.record import Record
from app.models.record_file import RecordFile


@dataclass(slots=True)
class OCRResultListRow:
    result: OCRResult


class OCRResultRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, ocr_result_id: int, user_id: int | None = None) -> OCRResult | None:
        statement = (
            select(OCRResult)
            .join(RecordFile, OCRResult.record_file_id == RecordFile.id)
            .join(Record, RecordFile.record_id == Record.id)
            .where(OCRResult.id == ocr_result_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_current_for_record_file(self, record_file_id: int, *, user_id: int | None = None) -> OCRResult | None:
        statement = (
            select(OCRResult)
            .join(RecordFile, OCRResult.record_file_id == RecordFile.id)
            .join(Record, RecordFile.record_id == Record.id)
            .where(OCRResult.record_file_id == record_file_id)
            .where(OCRResult.is_current.is_(True))
            .order_by(OCRResult.revision_number.desc(), OCRResult.id.desc())
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def get_latest_for_record_file(
        self,
        record_file_id: int,
        *,
        user_id: int | None = None,
        status: str | None = None,
    ) -> OCRResult | None:
        statement = (
            select(OCRResult)
            .join(RecordFile, OCRResult.record_file_id == RecordFile.id)
            .join(Record, RecordFile.record_id == Record.id)
            .where(OCRResult.record_file_id == record_file_id)
            .order_by(OCRResult.id.desc())
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        if status is not None:
            statement = statement.where(OCRResult.status == status)
        return self.session.scalar(statement)

    def list_for_record_file(
        self,
        *,
        record_file_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "revision_number",
        sort_order: str = "desc",
    ) -> tuple[list[OCRResultListRow], int]:
        filters = [OCRResult.record_file_id == record_file_id, Record.user_id == user_id]
        total_statement = (
            select(func.count(OCRResult.id))
            .select_from(OCRResult)
            .join(RecordFile, OCRResult.record_file_id == RecordFile.id)
            .join(Record, RecordFile.record_id == Record.id)
            .where(*filters)
        )
        total = self.session.scalar(total_statement) or 0

        sort_column = self._resolve_sort_column(sort_by)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        offset = (page - 1) * page_size
        statement = (
            select(OCRResult)
            .join(RecordFile, OCRResult.record_file_id == RecordFile.id)
            .join(Record, RecordFile.record_id == Record.id)
            .where(*filters)
            .order_by(order_clause, OCRResult.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = self.session.scalars(statement).all()
        return [OCRResultListRow(result=row) for row in rows], total

    def create_processing(
        self,
        record_file_id: int,
        provider_name: str,
    ) -> OCRResult:
        latest = self.get_latest_for_record_file(record_file_id)
        result = OCRResult(
            record_file_id=record_file_id,
            revision_number=1 if latest is None else latest.revision_number + 1,
            supersedes_ocr_result_id=latest.id if latest is not None else None,
            is_current=False,
            provider_name=provider_name,
            status=OCRStatus.PROCESSING,
            raw_text="",
            raw_payload={},
        )
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def mark_completed(
        self,
        ocr_result_id: int,
        provider_name: str,
        raw_text: str,
        raw_payload: dict,
    ) -> OCRResult:
        result = self.session.get(OCRResult, ocr_result_id)
        if result is None:
            raise ValueError("OCR result not found")
        self.session.query(OCRResult).filter(
            OCRResult.record_file_id == result.record_file_id,
            OCRResult.is_current.is_(True),
        ).update({"is_current": False}, synchronize_session=False)
        result.provider_name = provider_name
        result.status = OCRStatus.COMPLETED
        result.is_current = True
        result.raw_text = raw_text
        result.raw_payload = raw_payload
        self.session.commit()
        self.session.refresh(result)
        return result

    def mark_failed(self, ocr_result_id: int, error_code: str) -> OCRResult:
        result = self.session.get(OCRResult, ocr_result_id)
        if result is None:
            raise ValueError("OCR result not found")
        result.status = OCRStatus.FAILED
        result.raw_payload = {"error": error_code}
        self.session.commit()
        self.session.refresh(result)
        return result

    def _resolve_sort_column(self, sort_by: str):
        sort_columns = {
            "created_at": OCRResult.created_at,
            "id": OCRResult.id,
            "revision_number": OCRResult.revision_number,
        }
        return sort_columns.get(sort_by, OCRResult.revision_number)
