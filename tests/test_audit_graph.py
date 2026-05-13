from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import DocumentVersion, ExtractedDocument, Measurement, OCRResult, Record, RecordFile, User
from app.providers.base import LLMProvider, ProviderConfig
from app.repositories.knowledge_repository import DEFAULT_KNOWLEDGE_CHUNKS
from app.services.audit_graph.engine import AUDIT_GRAPH_EDGES, AuditGraphEngine
from app.services.audit_report_service import AuditReportService


class FakeReportLLMProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(ProviderConfig(provider_type="llm", name="fake_report_llm"))
        self.call_count = 0

    def complete(self, prompt: str) -> dict:
        return {"result": prompt}

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        self.call_count += 1
        return """
        {
          "title": "LLM 综合审计报告",
          "summary": "LLM 已基于证据生成审计摘要。",
          "sections": [
            {"id": "sources", "title": "一、数据来源", "content": "读取了文档和指标。"},
            {"id": "quality", "title": "二、文档质量", "content": "文档可追溯。"},
            {"id": "risks", "title": "三、风险与异常指标", "content": "血糖和 ALT 需要复核。"},
            {"id": "conflicts", "title": "四、跨文档一致性", "content": "存在糖尿病史表述复核点。"},
            {"id": "knowledge", "title": "五、审计知识依据", "content": "结合内置知识依据。"},
            {"id": "conclusion", "title": "六、审计结论", "content": "本报告用于审计复核，不替代医生诊断。"}
          ]
        }
        """


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
        "knowledge_chunks": DEFAULT_KNOWLEDGE_CHUNKS,
        "knowledge_queries": [],
        "knowledge_context": [],
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
    assert ("audit_router", "knowledge_retrieval_agent") in edges
    assert ("knowledge_retrieval_agent", "audit_router") in edges
    assert ("final_router", "audit_router") in edges

    final_state = AuditGraphEngine().run(_initial_graph_state())

    assert final_state["final_report"]["title"] == "多文档医疗审计综合报告"
    assert final_state["route_history"].count("audit_router") >= 5
    assert "knowledge_retrieval_agent" in final_state["route_history"]
    assert final_state["knowledge_context"]
    assert final_state["final_report"]["knowledge_context"]
    assert final_state["final_report"]["knowledge_sources"]
    assert final_state["final_report"]["rag_summary"]["source_count"] >= 1
    assert any(
        source["source_url"].startswith("https://www.msdmanuals.cn/home/")
        for source in final_state["final_report"]["knowledge_sources"]
        if source.get("source_url")
    )
    assert final_state["risk_findings"]
    assert all(finding["evidence_ids"] for finding in final_state["risk_findings"])
    assert any(item["kind"] == "knowledge_chunk" for item in final_state["evidence_items"])
    assert any(item["kind"] == "knowledge_chunk" and item.get("source_url") for item in final_state["evidence_items"])
    assert final_state["citation_issues"] == []
    assert final_state["safety_issues"] == []


def test_audit_graph_report_composer_calls_llm_once_when_provider_is_configured():
    llm_provider = FakeReportLLMProvider()

    final_state = AuditGraphEngine(llm_provider=llm_provider).run(_initial_graph_state())

    assert llm_provider.call_count == 1
    assert final_state["llm_call_count"] == 1
    assert final_state["llm_report_metadata"]["status"] == "completed"
    assert final_state["final_report"]["title"] == "LLM 综合审计报告"
    assert final_state["final_report"]["summary"] == "LLM 已基于证据生成审计摘要。"
    assert final_state["final_report"]["evidence_items"]


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
    assert completed.final_report["knowledge_sources"]
    assert any(source.get("source_url") for source in completed.final_report["knowledge_sources"])
    assert any(event.event_type == "edge_traversed" for event in events)
    assert any(event.event_type == "node_completed" and event.node_name == "risk_agent" for event in events)
    assert any(event.event_type == "node_completed" and event.node_name == "knowledge_retrieval_agent" for event in events)
    assert any(event.event_type == "report_ready" for event in events)
    assert {state.node_name for state in node_states} >= {
        "audit_router",
        "risk_agent",
        "knowledge_retrieval_agent",
        "persist_report",
    }


def test_audit_report_service_does_not_reexecute_processing_run():
    session = _build_session()
    user, version = _seed_document(session)
    service = AuditReportService(session=session, step_delay_seconds=0)

    run = service.create_run(
        user_id=user.id,
        selected_document_version_ids=[version.id],
        title="并发执行保护",
        max_iterations=8,
    )
    service.repository.mark_processing(run)

    result = service.execute_run(run_id=run.id, user_id=user.id)
    events = service.list_events(run_id=run.id, user_id=user.id)

    assert result.status == "processing"
    assert events == []
