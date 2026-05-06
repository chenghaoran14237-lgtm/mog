from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import DocumentVersion, ExtractedDocument, Measurement, OCRResult, Record, RecordFile, User
from app.services.audit_graph.engine import AUDIT_GRAPH_EDGES, AuditGraphEngine
from app.services.audit_report_service import AuditReportService


def _initial_graph_state() -> dict:
    return {
        "run_id": 1,
        "user_id": 1,
        "selected_document_version_ids": [10, 11],
        "documents": [
            {
                "document_version_id": 10,
                "document_id": 1,
                "display_name": "门诊病历",
                "document_category": "narrative_context",
                "report_date": "2026-04-01T09:00:00",
                "raw_text": "患者否认糖尿病史，近期乏力。",
                "normalized_payload": {"raw_text": "患者否认糖尿病史，近期乏力。"},
            },
            {
                "document_version_id": 11,
                "document_id": 2,
                "display_name": "生化检验报告",
                "document_category": "structured_metrics",
                "report_date": "2026-04-02T09:00:00",
                "raw_text": "空腹血糖 8.2 mmol/L，ALT 66 U/L。",
                "normalized_payload": {"raw_text": "空腹血糖 8.2 mmol/L，ALT 66 U/L。"},
            },
        ],
        "measurements": [
            {
                "document_version_id": 11,
                "name": "空腹血糖",
                "value_text": "8.2",
                "value_numeric": 8.2,
                "unit": "mmol/L",
                "observed_at": "2026-04-02T09:00:00",
            },
            {
                "document_version_id": 11,
                "name": "ALT",
                "value_text": "66",
                "value_numeric": 66.0,
                "unit": "U/L",
                "observed_at": "2026-04-02T09:00:00",
            },
        ],
        "timeline": [],
        "evidence_items": [],
        "quality_findings": [],
        "consistency_findings": [],
        "conflict_findings": [],
        "risk_findings": [],
        "compliance_findings": [],
        "report_draft": {},
        "citation_issues": [],
        "safety_issues": [],
        "final_report": None,
        "completed_agents": {},
        "route_history": [],
        "iteration_count": 0,
        "max_iterations": 8,
        "next_action": "audit_router",
        "stop_reason": None,
        "errors": [],
    }


def _build_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _seed_document(session):
    user = User(email="audit@example.com", password_hash="x")
    session.add(user)
    session.flush()
    record = Record(user_id=user.id, source="upload", status="normalized")
    session.add(record)
    session.flush()
    file = RecordFile(
        record_id=record.id,
        original_filename="lab.txt",
        display_name="生化检验报告",
        content_type="text/plain",
        size_bytes=32,
        content_bytes=b"lab",
        storage_provider="database_inline",
        storage_key="inline",
    )
    session.add(file)
    session.flush()
    ocr = OCRResult(
        record_file_id=file.id,
        revision_number=1,
        is_current=True,
        provider_name="plaintext",
        status="completed",
        raw_text="空腹血糖 8.2 mmol/L，ALT 66 U/L。",
        raw_payload={},
    )
    session.add(ocr)
    session.flush()
    document = ExtractedDocument(
        ocr_result_id=ocr.id,
        current_ocr_result_id=ocr.id,
        record_id=record.id,
        record_file_id=file.id,
        document_type="lab_report",
        document_category="structured_metrics",
        display_name="生化检验报告",
        status="normalized",
        normalized_payload={
            "raw_text": "空腹血糖 8.2 mmol/L，ALT 66 U/L。",
            "document_category": "structured_metrics",
            "measurements": [],
        },
    )
    session.add(document)
    session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        is_current=True,
        created_from_ocr_result_id=ocr.id,
        snapshot_hash="abc",
        normalized_payload=document.normalized_payload,
    )
    session.add(version)
    session.flush()
    session.add_all(
        [
            Measurement(
                extracted_document_id=document.id,
                document_version_id=version.id,
                name="空腹血糖",
                value_text="8.2",
                value_numeric=8.2,
                unit="mmol/L",
            ),
            Measurement(
                extracted_document_id=document.id,
                document_version_id=version.id,
                name="ALT",
                value_text="66",
                value_numeric=66.0,
                unit="U/L",
            ),
        ]
    )
    session.commit()
    return user, version


def test_audit_graph_is_cyclic_state_machine_and_generates_cited_report():
    edges = set(AUDIT_GRAPH_EDGES)

    assert ("audit_router", "risk_agent") in edges
    assert ("risk_agent", "audit_router") in edges
    assert ("final_router", "audit_router") in edges

    final_state = AuditGraphEngine().run(_initial_graph_state())

    assert final_state["final_report"]["title"] == "多文档医疗审计综合报告"
    assert final_state["route_history"].count("audit_router") >= 5
    assert final_state["risk_findings"]
    assert all(finding["evidence_ids"] for finding in final_state["risk_findings"])
    assert final_state["citation_issues"] == []
    assert final_state["safety_issues"] == []


def test_audit_report_service_persists_real_node_events_and_report():
    session = _build_session()
    user, version = _seed_document(session)
    service = AuditReportService(session=session, step_delay_seconds=0)

    run = service.create_run(
        user_id=user.id,
        selected_document_version_ids=[version.id],
        title="审计报告测试",
        max_iterations=8,
    )
    completed = service.execute_run(run_id=run.id, user_id=user.id)
    events = service.list_events(run_id=run.id, user_id=user.id)
    node_states = service.list_node_states(run_id=run.id, user_id=user.id)

    assert completed.status == "completed"
    assert completed.final_report["title"] == "多文档医疗审计综合报告"
    assert any(event.event_type == "edge_traversed" for event in events)
    assert any(event.event_type == "node_completed" and event.node_name == "risk_agent" for event in events)
    assert any(event.event_type == "report_ready" for event in events)
    assert {state.node_name for state in node_states} >= {"audit_router", "risk_agent", "persist_report"}
