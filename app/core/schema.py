from __future__ import annotations

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import selectinload

from app.core.db import Base, SessionLocal, engine
from app.models import (  # noqa: F401
    AnalysisRun,
    AuditReportEvent,
    AuditReportNodeState,
    AuditReportRun,
    DocumentVersion,
    ExtractedDocument,
    InsightMessage,
    InsightSession,
    Measurement,
    RecordFile,
)
from app.services.document_semantics import (
    STRUCTURED_METRICS,
    extract_report_date,
    infer_document_category,
    parse_datetime_value,
)


def ensure_database_schema() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _backfill_semantic_fields()


def _ensure_columns() -> None:
    inspector = inspect(engine)

    with engine.begin() as connection:
        if inspector.has_table("record_files"):
            record_file_columns = {column["name"]: column for column in inspector.get_columns("record_files")}
            content_bytes_column = record_file_columns.get("content_bytes")
            if (
                content_bytes_column is not None
                and engine.dialect.name == "mysql"
                and "LONGBLOB" not in str(content_bytes_column["type"]).upper()
            ):
                connection.execute(text("ALTER TABLE record_files MODIFY content_bytes LONGBLOB NOT NULL"))

        extracted_document_columns = {column["name"] for column in inspector.get_columns("extracted_documents")}
        if "document_category" not in extracted_document_columns:
            connection.execute(text("ALTER TABLE extracted_documents ADD COLUMN document_category VARCHAR(64) DEFAULT 'narrative_context'"))
        if "report_date" not in extracted_document_columns:
            connection.execute(text("ALTER TABLE extracted_documents ADD COLUMN report_date DATETIME"))

        document_version_columns = {column["name"] for column in inspector.get_columns("document_versions")}
        if "report_date" not in document_version_columns:
            connection.execute(text("ALTER TABLE document_versions ADD COLUMN report_date DATETIME"))

        measurement_columns = {column["name"] for column in inspector.get_columns("measurements")}
        if "observed_at" not in measurement_columns:
            connection.execute(text("ALTER TABLE measurements ADD COLUMN observed_at DATETIME"))


def _backfill_semantic_fields() -> None:
    session = SessionLocal()
    try:
        documents = list(
            session.scalars(
                select(ExtractedDocument).options(
                    selectinload(ExtractedDocument.versions).selectinload(DocumentVersion.measurements),
                )
            ).all()
        )

        for document in documents:
            current_version = next((version for version in document.versions if version.is_current), None)
            current_payload: dict = {}
            current_raw_text = ""
            current_report_date = None
            current_category = document.document_category
            for version in document.versions:
                version_payload = version.normalized_payload or {}
                version_raw_text = str(version_payload.get("raw_text") or document.normalized_payload.get("raw_text") or "")
                payload_measurements = version_payload.get("measurements") if isinstance(version_payload, dict) else []
                measurement_input = (
                    payload_measurements
                    if isinstance(payload_measurements, list) and payload_measurements
                    else [_serialize_measurement(measurement) for measurement in version.measurements]
                )
                version_report_date = (
                    parse_datetime_value(version_payload.get("report_date"))
                    or version.report_date
                    or extract_report_date(version_raw_text, version_payload)
                )
                version_category = infer_document_category(
                    raw_text=version_raw_text,
                    measurements=measurement_input,
                    document_type=None,
                    normalized_payload=version_payload,
                )

                if version.report_date != version_report_date:
                    version.report_date = version_report_date

                if version_category == STRUCTURED_METRICS:
                    effective_observed_at = version_report_date
                    for measurement in version.measurements:
                        if measurement.observed_at != effective_observed_at:
                            measurement.observed_at = effective_observed_at
                    serialized_measurements = [_serialize_measurement(measurement) for measurement in version.measurements]
                else:
                    serialized_measurements = []
                    for measurement in list(version.measurements):
                        session.delete(measurement)

                sanitized_payload = dict(version_payload)
                sanitized_payload["document_category"] = version_category
                sanitized_payload["report_date"] = version_report_date.isoformat() if version_report_date else None
                sanitized_payload["measurements"] = serialized_measurements
                sanitized_payload["measurement_count"] = len(serialized_measurements)
                version.normalized_payload = sanitized_payload

                if version.is_current:
                    current_payload = dict(sanitized_payload)
                    current_raw_text = version_raw_text
                    current_report_date = version_report_date
                    current_category = version_category

            if current_version is None:
                fallback_payload = document.normalized_payload or {}
                fallback_raw_text = str(fallback_payload.get("raw_text") or "")
                fallback_measurements = fallback_payload.get("measurements") if isinstance(fallback_payload, dict) else []
                current_report_date = (
                    parse_datetime_value(fallback_payload.get("report_date") if isinstance(fallback_payload, dict) else None)
                    or document.report_date
                    or extract_report_date(fallback_raw_text, fallback_payload if isinstance(fallback_payload, dict) else None)
                )
                current_category = infer_document_category(
                    raw_text=fallback_raw_text,
                    measurements=fallback_measurements if isinstance(fallback_measurements, list) else [],
                    document_type=None,
                    normalized_payload=fallback_payload if isinstance(fallback_payload, dict) else {},
                )
                current_payload = dict(fallback_payload)
                current_payload["document_category"] = current_category
                current_payload["report_date"] = current_report_date.isoformat() if current_report_date else None
                if current_category != STRUCTURED_METRICS:
                    current_payload["measurements"] = []
                    current_payload["measurement_count"] = 0
                else:
                    current_payload["measurement_count"] = len(current_payload.get("measurements") or [])

            document.document_category = current_category
            document.report_date = current_report_date
            document.document_type = "lab_report" if current_category == STRUCTURED_METRICS else "clinical_note"
            document.normalized_payload = current_payload or {
                "raw_text": current_raw_text,
                "document_category": current_category,
                "report_date": current_report_date.isoformat() if current_report_date else None,
                "measurements": [],
                "measurement_count": 0,
            }

        session.commit()
    finally:
        session.close()


def _serialize_measurement(measurement: Measurement) -> dict:
    return {
        "name": measurement.name,
        "value_text": measurement.value_text,
        "value_numeric": measurement.value_numeric,
        "unit": measurement.unit,
        "observed_at": measurement.observed_at.isoformat() if measurement.observed_at else None,
    }
