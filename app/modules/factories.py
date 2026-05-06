from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.file_upload_service import FileUploadService
from app.services.ocr_query_service import OCRQueryService
from app.services.provider_gateway import ProviderGateway
from app.services.query_service import QueryService
from app.services.security import PasswordHasher, TokenService
from app.services.task_service import TaskService


def build_provider_gateway(session: Session) -> ProviderGateway:
    return ProviderGateway(
        provider_registry=ProviderRegistry(),
        provider_event_repository=ProviderEventRepository(session),
    )


def build_file_upload_service(session: Session) -> FileUploadService:
    return FileUploadService(
        RecordRepository(session),
        build_provider_gateway(session),
    )


def build_task_service(session: Session) -> TaskService:
    return TaskService(
        task_repository=TaskRepository(session),
        record_repository=RecordRepository(session),
        ocr_result_repository=OCRResultRepository(session),
        extracted_document_repository=ExtractedDocumentRepository(session),
        document_version_repository=DocumentVersionRepository(session),
        measurement_repository=MeasurementRepository(session),
        provider_event_repository=ProviderEventRepository(session),
        provider_registry=ProviderRegistry(),
    )


def build_ocr_query_service(session: Session) -> OCRQueryService:
    return OCRQueryService(
        record_repository=RecordRepository(session),
        ocr_result_repository=OCRResultRepository(session),
    )


def build_query_service(session: Session) -> QueryService:
    return QueryService(
        record_repository=RecordRepository(session),
        extracted_document_repository=ExtractedDocumentRepository(session),
        document_version_repository=DocumentVersionRepository(session),
        measurement_repository=MeasurementRepository(session),
    )


def build_auth_service(session: Session, settings: Settings) -> AuthService:
    return AuthService(
        user_repository=UserRepository(session),
        password_hasher=PasswordHasher(),
        token_service=TokenService(
            secret_key=settings.auth_secret_key,
            expire_minutes=settings.auth_token_expire_minutes,
        ),
    )
