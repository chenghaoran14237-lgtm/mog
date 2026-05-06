from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_report_event import AuditReportEvent
from app.models.audit_report_node_state import AuditReportNodeState
from app.models.audit_report_run import AuditReportRun


class AuditReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        user_id: int,
        selected_document_version_ids: list[int],
        title: str | None,
        max_iterations: int,
    ) -> AuditReportRun:
        run = AuditReportRun(
            user_id=user_id,
            title=title,
            status="pending",
            selected_document_version_ids=selected_document_version_ids,
            graph_state={},
            final_report=None,
            iteration_count=0,
            max_iterations=max_iterations,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, *, run_id: int, user_id: int) -> AuditReportRun | None:
        return self.session.scalar(
            select(AuditReportRun).where(AuditReportRun.id == run_id, AuditReportRun.user_id == user_id)
        )

    def list_runs(self, *, user_id: int, limit: int = 20) -> list[AuditReportRun]:
        return list(
            self.session.scalars(
                select(AuditReportRun)
                .where(AuditReportRun.user_id == user_id)
                .order_by(AuditReportRun.created_at.desc(), AuditReportRun.id.desc())
                .limit(limit)
            ).all()
        )

    def mark_processing(self, run: AuditReportRun) -> AuditReportRun:
        run.status = "processing"
        run.started_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update_graph_state(self, run: AuditReportRun, graph_state: dict) -> AuditReportRun:
        run.graph_state = graph_state
        run.iteration_count = int(graph_state.get("iteration_count") or 0)
        run.stop_reason = graph_state.get("stop_reason")
        self.session.commit()
        self.session.refresh(run)
        return run

    def mark_completed(self, run: AuditReportRun, *, graph_state: dict, final_report: dict) -> AuditReportRun:
        run.status = "completed"
        run.graph_state = graph_state
        run.final_report = final_report
        run.iteration_count = int(graph_state.get("iteration_count") or 0)
        run.stop_reason = graph_state.get("stop_reason") or "completed"
        run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def mark_failed(self, run: AuditReportRun, *, message: str, graph_state: dict | None = None) -> AuditReportRun:
        run.status = "failed"
        run.error_message = message[:2000]
        if graph_state is not None:
            run.graph_state = graph_state
        run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def append_event(
        self,
        *,
        run_id: int,
        user_id: int,
        event_type: str,
        node_name: str | None = None,
        edge_source: str | None = None,
        edge_target: str | None = None,
        status: str | None = None,
        message: str | None = None,
        payload: dict | None = None,
    ) -> AuditReportEvent:
        sequence = self._next_sequence(run_id)
        event = AuditReportEvent(
            run_id=run_id,
            user_id=user_id,
            sequence=sequence,
            event_type=event_type,
            node_name=node_name,
            edge_source=edge_source,
            edge_target=edge_target,
            status=status,
            message=message,
            payload=payload or {},
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_events(self, *, run_id: int, user_id: int) -> list[AuditReportEvent]:
        return list(
            self.session.scalars(
                select(AuditReportEvent)
                .where(AuditReportEvent.run_id == run_id, AuditReportEvent.user_id == user_id)
                .order_by(AuditReportEvent.sequence.asc(), AuditReportEvent.id.asc())
            ).all()
        )

    def upsert_node_state(
        self,
        *,
        run_id: int,
        user_id: int,
        node_name: str,
        status: str,
        last_event_id: int | None,
        output: dict,
    ) -> AuditReportNodeState:
        node_state = self.session.scalar(
            select(AuditReportNodeState).where(
                AuditReportNodeState.run_id == run_id,
                AuditReportNodeState.user_id == user_id,
                AuditReportNodeState.node_name == node_name,
            )
        )
        if node_state is None:
            node_state = AuditReportNodeState(
                run_id=run_id,
                user_id=user_id,
                node_name=node_name,
                status=status,
                visit_count=1,
                last_event_id=last_event_id,
                output=output,
            )
            self.session.add(node_state)
        else:
            node_state.status = status
            node_state.visit_count += 1
            node_state.last_event_id = last_event_id
            node_state.output = output
        self.session.commit()
        self.session.refresh(node_state)
        return node_state

    def list_node_states(self, *, run_id: int, user_id: int) -> list[AuditReportNodeState]:
        return list(
            self.session.scalars(
                select(AuditReportNodeState)
                .where(AuditReportNodeState.run_id == run_id, AuditReportNodeState.user_id == user_id)
                .order_by(AuditReportNodeState.id.asc())
            ).all()
        )

    def _next_sequence(self, run_id: int) -> int:
        current = self.session.scalar(
            select(func.max(AuditReportEvent.sequence)).where(AuditReportEvent.run_id == run_id)
        )
        return int(current or 0) + 1
