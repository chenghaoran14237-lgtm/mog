from collections import Counter
import math

from app.core.errors import APIError
from app.repositories.ocr_result_repository import OCRResultListRow, OCRResultRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.ocr import OCRResultListResponse, OCRResultResponse, OCRRevisionDiffResponse
from app.schemas.query import PaginationResponse


class OCRQueryService:
    def __init__(
        self,
        *,
        record_repository: RecordRepository,
        ocr_result_repository: OCRResultRepository,
    ) -> None:
        self.record_repository = record_repository
        self.ocr_result_repository = ocr_result_repository

    def get_revision(self, ocr_result_id: int, *, current_user_id: int) -> OCRResultResponse:
        revision = self.ocr_result_repository.get_by_id(ocr_result_id, user_id=current_user_id)
        if revision is None:
            raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")
        return OCRResultResponse.model_validate(revision)

    def get_current_revision_for_file(self, record_file_id: int, *, current_user_id: int) -> OCRResultResponse:
        self._ensure_file_exists(record_file_id, current_user_id)
        revision = self.ocr_result_repository.get_current_for_record_file(record_file_id, user_id=current_user_id)
        if revision is None:
            raise APIError(status_code=404, code="current_ocr_revision_not_found", message="Current OCR revision not found")
        return OCRResultResponse.model_validate(revision)

    def list_revisions_for_file(
        self,
        record_file_id: int,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "revision_number",
        sort_order: str = "desc",
    ) -> OCRResultListResponse:
        self._ensure_file_exists(record_file_id, current_user_id)
        rows, total = self.ocr_result_repository.list_for_record_file(
            record_file_id=record_file_id,
            user_id=current_user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return OCRResultListResponse(
            items=[self._build_revision_response(row) for row in rows],
            pagination=self._build_pagination(page, page_size, total, sort_by, sort_order),
        )

    def compare_revisions(self, from_ocr_result_id: int, to_ocr_result_id: int, *, current_user_id: int) -> OCRRevisionDiffResponse:
        from_revision = self.ocr_result_repository.get_by_id(from_ocr_result_id, user_id=current_user_id)
        to_revision = self.ocr_result_repository.get_by_id(to_ocr_result_id, user_id=current_user_id)
        if from_revision is None or to_revision is None:
            raise APIError(status_code=404, code="ocr_result_not_found", message="OCR result not found")
        if from_revision.record_file_id != to_revision.record_file_id:
            raise APIError(status_code=409, code="ocr_revision_compare_scope_mismatch", message="OCR revisions must belong to the same file")

        from_lines = [line.strip() for line in from_revision.raw_text.splitlines() if line.strip()]
        to_lines = [line.strip() for line in to_revision.raw_text.splitlines() if line.strip()]
        from_counter = Counter(from_lines)
        to_counter = Counter(to_lines)

        added_lines: list[str] = []
        removed_lines: list[str] = []
        for line, count in (to_counter - from_counter).items():
            added_lines.extend([line] * count)
        for line, count in (from_counter - to_counter).items():
            removed_lines.extend([line] * count)

        return OCRRevisionDiffResponse(
            from_ocr_result_id=from_revision.id,
            to_ocr_result_id=to_revision.id,
            from_revision_number=from_revision.revision_number,
            to_revision_number=to_revision.revision_number,
            provider_changed=from_revision.provider_name != to_revision.provider_name,
            status_changed=from_revision.status != to_revision.status,
            raw_text_changed=from_revision.raw_text != to_revision.raw_text,
            raw_text_length_delta=len(to_revision.raw_text) - len(from_revision.raw_text),
            line_count_delta=len(to_lines) - len(from_lines),
            added_lines=added_lines[:20],
            removed_lines=removed_lines[:20],
        )

    def _ensure_file_exists(self, record_file_id: int, current_user_id: int) -> None:
        record_file = self.record_repository.get_record_file_by_id(record_file_id, user_id=current_user_id)
        if record_file is None:
            raise APIError(status_code=404, code="record_file_not_found", message="Record file not found")

    def _build_revision_response(self, row: OCRResultListRow) -> OCRResultResponse:
        return OCRResultResponse.model_validate(row.result)

    def _build_pagination(self, page: int, page_size: int, total_items: int, sort_by: str, sort_order: str) -> PaginationResponse:
        total_pages = math.ceil(total_items / page_size) if total_items else 0
        return PaginationResponse(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages, sort_by=sort_by, sort_order=sort_order)
