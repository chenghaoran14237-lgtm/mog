from __future__ import annotations

from app.modules.factories import (
    build_file_upload_service,
    build_ocr_query_service,
    build_query_service,
    build_task_service,
)
from app.schemas.file_upload import FileUploadResponse
from app.schemas.ocr import OCRResultListResponse, OCRResultResponse, OCRRevisionDiffResponse
from app.schemas.query import DocumentVersionDetailResponse, DocumentVersionListResponse
from app.schemas.task import TaskResultResponse, TaskSubmissionResponse


class PerceptionModuleAPI:
    def __init__(self, *, file_upload_service, task_service, ocr_query_service, query_service) -> None:
        self.file_upload_service = file_upload_service
        self.task_service = task_service
        self.ocr_query_service = ocr_query_service
        self.query_service = query_service

    @classmethod
    def from_session(cls, session) -> "PerceptionModuleAPI":
        return cls(
            file_upload_service=build_file_upload_service(session),
            task_service=build_task_service(session),
            ocr_query_service=build_ocr_query_service(session),
            query_service=build_query_service(session),
        )

    def upload(
        self,
        *,
        user_id: int,
        request_id: str | None,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
        content_bytes: bytes,
    ) -> FileUploadResponse:
        return self.file_upload_service.create_upload(
            user_id=user_id,
            request_id=request_id,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            content_bytes=content_bytes,
        )

    def run_ocr(
        self,
        *,
        current_user_id: int,
        record_file_id: int,
        request_id: str | None,
        force_reprocess: bool = False,
    ) -> TaskSubmissionResponse:
        return self.task_service.submit_ocr_task(
            current_user_id=current_user_id,
            record_file_id=record_file_id,
            request_id=request_id,
            force_reprocess=force_reprocess,
        )

    def list_ocr_revisions(
        self,
        *,
        record_file_id: int,
        current_user_id: int,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "revision_number",
        sort_order: str = "desc",
    ) -> OCRResultListResponse:
        return self.ocr_query_service.list_revisions_for_file(
            record_file_id,
            current_user_id=current_user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_current_ocr_revision(self, *, record_file_id: int, current_user_id: int) -> OCRResultResponse:
        return self.ocr_query_service.get_current_revision_for_file(record_file_id, current_user_id=current_user_id)

    def get_ocr_revision(self, *, ocr_result_id: int, current_user_id: int) -> OCRResultResponse:
        return self.ocr_query_service.get_revision(ocr_result_id, current_user_id=current_user_id)

    def compare_ocr_revisions(self, *, from_id: int, to_id: int, current_user_id: int) -> OCRRevisionDiffResponse:
        return self.ocr_query_service.compare_revisions(from_id, to_id, current_user_id=current_user_id)

    def normalize_selected_ocr_revision(
        self,
        *,
        current_user_id: int,
        ocr_result_id: int,
        request_id: str | None,
        force_reprocess: bool = False,
    ) -> TaskSubmissionResponse:
        return self.task_service.submit_normalization_task(
            current_user_id=current_user_id,
            ocr_result_id=ocr_result_id,
            request_id=request_id,
            force_reprocess=force_reprocess,
        )

    def list_document_versions(
        self,
        *,
        document_id: int,
        current_user_id: int,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "version_number",
        sort_order: str = "desc",
    ) -> DocumentVersionListResponse:
        return self.query_service.list_document_versions(
            document_id=document_id,
            current_user_id=current_user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_document_version(self, *, version_id: int, current_user_id: int) -> DocumentVersionDetailResponse:
        return self.query_service.get_document_version(version_id, current_user_id=current_user_id)

    def get_current_document_version(self, *, document_id: int, current_user_id: int) -> DocumentVersionDetailResponse:
        return self.query_service.get_current_document_version(document_id, current_user_id=current_user_id)

    def get_task_result(self, *, current_user_id: int, task_id: int) -> TaskResultResponse:
        return self.task_service.get_task_result(current_user_id=current_user_id, task_id=task_id)
