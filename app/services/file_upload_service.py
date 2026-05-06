from app.repositories.record_repository import RecordRepository
from app.services.provider_gateway import ProviderGateway
from app.schemas.file_upload import FileUploadResponse, RecordFileResponse, RecordResponse


class FileUploadService:
    def __init__(self, record_repository: RecordRepository, provider_gateway: ProviderGateway) -> None:
        self.record_repository = record_repository
        self.provider_gateway = provider_gateway

    def create_upload(
        self,
        user_id: int,
        request_id: str | None,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
        content_bytes: bytes,
        display_name: str | None = None,
    ) -> FileUploadResponse:
        storage_result = self.provider_gateway.store_file(
            user_id=user_id,
            task_id=None,
            request_id=request_id,
            resource_id=0,
            original_filename=original_filename,
            content_type=content_type,
            content_bytes=content_bytes,
        )
        record, record_file = self.record_repository.create_record_with_file(
            user_id=user_id,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            content_bytes=storage_result.content_bytes,
            storage_provider=storage_result.provider_name,
            storage_key=storage_result.storage_key,
            display_name=display_name,
        )
        return FileUploadResponse(
            record=RecordResponse.model_validate(record),
            file=RecordFileResponse.model_validate(record_file),
        )
