from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import SessionLocal
from app.core.observability import log_event
from app.providers.registry import ProviderRegistry
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.extracted_document_repository import ExtractedDocumentRepository
from app.repositories.ocr_result_repository import OCRResultRepository
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.repositories.task_repository import TaskRepository
from app.services.task_processor import TaskProcessor


def render_database_url(database_url) -> str:
    if hasattr(database_url, "render_as_string"):
        return database_url.render_as_string(hide_password=False)
    return str(database_url)


def run_task(task_id: int, request_id: str | None = None, database_url: str | None = None) -> None:
    engine = None
    local_sessionmaker = SessionLocal
    if database_url is not None:
        engine = create_engine(database_url, future=True, pool_pre_ping=True)
        local_sessionmaker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = local_sessionmaker()
    try:
        processor = TaskProcessor(
            task_repository=TaskRepository(session),
            record_repository=RecordRepository(session),
            ocr_result_repository=OCRResultRepository(session),
            extracted_document_repository=ExtractedDocumentRepository(session),
            document_version_repository=DocumentVersionRepository(session),
            provider_event_repository=ProviderEventRepository(session),
            provider_registry=ProviderRegistry(),
        )
        processor.process_task(task_id, request_id=request_id)
    finally:
        session.close()
        if engine is not None:
            engine.dispose()
        log_event("task_runner_finished", task_id=task_id)
