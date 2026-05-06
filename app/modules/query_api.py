from __future__ import annotations

from app.modules.factories import build_query_service
from app.schemas.query import (
    DocumentVersionDetailResponse,
    DocumentVersionDiffResponse,
    DocumentVersionListResponse,
    ExtractedDocumentDetailResponse,
    ExtractedDocumentListResponse,
    MeasurementListResponse,
    QuerySelectionDocumentVersion,
    QuerySelectionResponse,
)


class QueryModuleAPI:
    def __init__(self, *, query_service) -> None:
        self.query_service = query_service

    @classmethod
    def from_session(cls, session) -> "QueryModuleAPI":
        return cls(query_service=build_query_service(session))

    def list_documents(self, **kwargs) -> ExtractedDocumentListResponse:
        return self.query_service.list_documents(**kwargs)

    def get_document(self, *, document_id: int, current_user_id: int) -> ExtractedDocumentDetailResponse:
        return self.query_service.get_document(document_id, current_user_id=current_user_id)

    def list_document_versions(self, **kwargs) -> DocumentVersionListResponse:
        return self.query_service.list_document_versions(**kwargs)

    def get_document_version(self, *, version_id: int, current_user_id: int) -> DocumentVersionDetailResponse:
        return self.query_service.get_document_version(version_id, current_user_id=current_user_id)

    def get_current_document_version(self, *, document_id: int, current_user_id: int) -> DocumentVersionDetailResponse:
        return self.query_service.get_current_document_version(document_id, current_user_id=current_user_id)

    def compare_document_versions(self, *, from_version_id: int, to_version_id: int, current_user_id: int) -> DocumentVersionDiffResponse:
        return self.query_service.compare_document_versions(from_version_id, to_version_id, current_user_id=current_user_id)

    def list_measurements(self, **kwargs) -> MeasurementListResponse:
        return self.query_service.list_measurements(**kwargs)

    def select_document_versions(
        self,
        *,
        current_user_id: int,
        document_version_ids: list[int],
        requested_measurements: list[str] | None = None,
    ) -> QuerySelectionResponse:
        selected_versions: list[QuerySelectionDocumentVersion] = []
        selected_measurements = []
        requested_names = {name.strip().lower() for name in (requested_measurements or []) if name.strip()}

        for version_id in list(dict.fromkeys(document_version_ids)):
            version = self.query_service.get_document_version(version_id, current_user_id=current_user_id)
            selected_versions.append(
                QuerySelectionDocumentVersion(
                    version=version,
                    selected_measurements=[
                        item for item in version.measurements
                        if not requested_names or item.name.lower() in requested_names
                    ],
                )
            )
            selected_measurements.extend(
                item for item in version.measurements
                if not requested_names or item.name.lower() in requested_names
            )

        return QuerySelectionResponse(
            selected_document_version_ids=[item.version.id for item in selected_versions],
            selected_versions=selected_versions,
            selected_measurements=selected_measurements,
            source_count=len(selected_versions),
        )
