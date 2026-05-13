from __future__ import annotations

from time import sleep
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.document_version import DocumentVersion
from app.models.extracted_document import ExtractedDocument
from app.models.record import Record
from app.repositories.audit_report_repository import AuditReportRepository
from app.repositories.knowledge_repository import (
    DEFAULT_KNOWLEDGE_CHUNKS,
    KnowledgeRepository,
    knowledge_chunk_to_dict,
)
from app.services.audit_graph.engine import AuditGraphEngine
from app.services.audit_graph.state import AuditGraphState, create_initial_state


class AuditReportService:
    def __init__(
        self,
        *,
        session: Session,
        repository: AuditReportRepository | None = None,
        graph_engine: AuditGraphEngine | None = None,
        step_delay_seconds: float = 0.15,
    ) -> None:
        self.session = session
        self.repository = repository or AuditReportRepository(session)
        self.graph_engine = graph_engine or AuditGraphEngine()
        self.step_delay_seconds = step_delay_seconds

    def create_run(
        self,
        *,
        user_id: int,
        selected_document_version_ids: list[int],
        title: str | None = None,
        max_iterations: int = 8,
    ):
        if not selected_document_version_ids:
            raise ValueError("At least one document version must be selected")
        deduped_ids = list(dict.fromkeys(int(value) for value in selected_document_version_ids))
        return self.repository.create_run(
            user_id=user_id,
            selected_document_version_ids=deduped_ids,
            title=title,
            max_iterations=max_iterations,
        )

    def execute_run(self, *, run_id: int, user_id: int):
        run = self.repository.get_run(run_id=run_id, user_id=user_id)
        if run is None:
            raise ValueError("Audit report run not found")
        if run.status in {"processing", "completed"}:
            return run

        state: AuditGraphState | None = None
        try:
            self.repository.mark_processing(run)
            state = self._build_initial_state(run_id=run.id, user_id=user_id)
            self.repository.update_graph_state(run, state)

            last_node = "__start__"
            for step in self.graph_engine.stream(state):
                self.repository.append_event(
                    run_id=run.id,
                    user_id=user_id,
                    event_type="edge_traversed",
                    edge_source=step.edge_source,
                    edge_target=step.edge_target,
                    status="completed",
                    payload={"route_history_length": len(step.state.get("route_history") or [])},
                )
                self.repository.append_event(
                    run_id=run.id,
                    user_id=user_id,
                    event_type="node_started",
                    node_name=step.node_name,
                    status="processing",
                    payload={"visit_count": (step.state.get("completed_agents") or {}).get(step.node_name, 0)},
                )
                completed_event = self.repository.append_event(
                    run_id=run.id,
                    user_id=user_id,
                    event_type="node_completed",
                    node_name=step.node_name,
                    status="completed",
                    payload=_summarize_node_output(step.output),
                )
                self.repository.upsert_node_state(
                    run_id=run.id,
                    user_id=user_id,
                    node_name=step.node_name,
                    status="completed",
                    last_event_id=completed_event.id,
                    output=_summarize_node_output(step.output),
                )
                state = step.state
                last_node = step.node_name
                self.repository.update_graph_state(run, state)
                if self.step_delay_seconds > 0:
                    sleep(self.step_delay_seconds)

            final_report = (state or {}).get("final_report") or (state or {}).get("report_draft") or {}
            self.repository.append_event(
                run_id=run.id,
                user_id=user_id,
                event_type="edge_traversed",
                edge_source=last_node,
                edge_target="__end__",
                status="completed",
                payload={},
            )
            self.repository.append_event(
                run_id=run.id,
                user_id=user_id,
                event_type="report_ready",
                node_name="persist_report",
                status="completed",
                message="审计报告已生成",
                payload={"section_count": len(final_report.get("sections") or [])},
            )
            return self.repository.mark_completed(run, graph_state=state or {}, final_report=final_report)
        except Exception as exc:
            self.repository.append_event(
                run_id=run.id,
                user_id=user_id,
                event_type="run_failed",
                status="failed",
                message=str(exc),
                payload={},
            )
            return self.repository.mark_failed(run, message=str(exc), graph_state=state)

    def get_run(self, *, run_id: int, user_id: int):
        run = self.repository.get_run(run_id=run_id, user_id=user_id)
        if run is None:
            raise ValueError("Audit report run not found")
        return run

    def list_runs(self, *, user_id: int, limit: int = 20):
        return self.repository.list_runs(user_id=user_id, limit=limit)

    def list_events(self, *, run_id: int, user_id: int):
        self.get_run(run_id=run_id, user_id=user_id)
        return self.repository.list_events(run_id=run_id, user_id=user_id)

    def list_node_states(self, *, run_id: int, user_id: int):
        self.get_run(run_id=run_id, user_id=user_id)
        return self.repository.list_node_states(run_id=run_id, user_id=user_id)

    def _build_initial_state(self, *, run_id: int, user_id: int) -> AuditGraphState:
        run = self.repository.get_run(run_id=run_id, user_id=user_id)
        if run is None:
            raise ValueError("Audit report run not found")
        versions = self._load_versions(user_id=user_id, version_ids=run.selected_document_version_ids)
        knowledge_chunks = self._load_knowledge_chunks()
        found_ids = {version.id for version in versions}
        missing_ids = [version_id for version_id in run.selected_document_version_ids if version_id not in found_ids]
        if missing_ids:
            raise ValueError(f"Document versions not found or not accessible: {missing_ids}")

        documents: list[dict[str, Any]] = []
        measurements: list[dict[str, Any]] = []
        for version in versions:
            document = version.document
            payload = version.normalized_payload or {}
            raw_text = str(payload.get("raw_text") or document.normalized_payload.get("raw_text") or "")
            documents.append(
                {
                    "document_version_id": version.id,
                    "document_id": document.id,
                    "record_id": document.record_id,
                    "record_file_id": document.record_file_id,
                    "display_name": document.display_name,
                    "document_type": document.document_type,
                    "document_category": payload.get("document_category") or document.document_category,
                    "report_date": _iso(version.report_date or document.report_date),
                    "raw_text": raw_text,
                    "normalized_payload": payload,
                }
            )
            if version.measurements:
                for measurement in version.measurements:
                    measurements.append(
                        {
                            "id": measurement.id,
                            "document_version_id": version.id,
                            "document_id": document.id,
                            "record_id": document.record_id,
                            "record_file_id": document.record_file_id,
                            "name": measurement.name,
                            "value_text": measurement.value_text,
                            "value_numeric": measurement.value_numeric,
                            "unit": measurement.unit,
                            "observed_at": _iso(measurement.observed_at or version.report_date or document.report_date),
                        }
                    )
            else:
                for measurement in payload.get("measurements") or []:
                    if isinstance(measurement, dict):
                        measurements.append(
                            {
                                **measurement,
                                "document_version_id": version.id,
                                "document_id": document.id,
                                "record_id": document.record_id,
                                "record_file_id": document.record_file_id,
                            }
                        )
        return create_initial_state(
            run_id=run_id,
            user_id=user_id,
            selected_document_version_ids=list(run.selected_document_version_ids),
            documents=documents,
            measurements=measurements,
            knowledge_chunks=knowledge_chunks,
            max_iterations=run.max_iterations,
        )

    def _load_versions(self, *, user_id: int, version_ids: list[int]) -> list[DocumentVersion]:
        if not version_ids:
            return []
        statement = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.measurements), selectinload(DocumentVersion.document))
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(DocumentVersion.id.in_(version_ids), Record.user_id == user_id)
        )
        versions = list(self.session.scalars(statement).all())
        by_id = {version.id: version for version in versions}
        return [by_id[version_id] for version_id in version_ids if version_id in by_id]

    def _load_knowledge_chunks(self) -> list[dict[str, Any]]:
        try:
            chunks = KnowledgeRepository(self.session).ensure_default_chunks()
            return [knowledge_chunk_to_dict(chunk) for chunk in chunks]
        except SQLAlchemyError:
            self.session.rollback()
            return [dict(item) for item in DEFAULT_KNOWLEDGE_CHUNKS]


def _summarize_node_output(output: dict) -> dict:
    summary: dict[str, Any] = {}
    for key, value in output.items():
        if key in {"documents", "measurements", "evidence_items", "knowledge_context", "route_history"} and isinstance(value, list):
            summary[f"{key}_count"] = len(value)
        elif key in {
            "next_action",
            "stop_reason",
            "iteration_count",
            "quality_gate",
            "citation_issues",
            "safety_issues",
            "final_report",
            "report_draft",
        }:
            summary[key] = value
        elif key.endswith("_findings") and isinstance(value, list):
            summary[f"{key}_count"] = len(value)
    return summary


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
