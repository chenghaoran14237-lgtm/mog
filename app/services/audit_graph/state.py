from __future__ import annotations

from typing import Any, TypedDict


class AuditGraphState(TypedDict, total=False):
    run_id: int
    user_id: int
    selected_document_version_ids: list[int]
    documents: list[dict[str, Any]]
    measurements: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    quality_findings: list[dict[str, Any]]
    consistency_findings: list[dict[str, Any]]
    conflict_findings: list[dict[str, Any]]
    risk_findings: list[dict[str, Any]]
    compliance_findings: list[dict[str, Any]]
    report_draft: dict[str, Any]
    citation_issues: list[dict[str, Any]]
    safety_issues: list[dict[str, Any]]
    final_report: dict[str, Any] | None
    quality_gate: dict[str, Any]
    completed_agents: dict[str, int]
    route_history: list[str]
    iteration_count: int
    max_iterations: int
    next_action: str
    needs_report_revision: bool
    stop_reason: str | None
    errors: list[dict[str, Any]]


def create_initial_state(
    *,
    run_id: int,
    user_id: int,
    selected_document_version_ids: list[int],
    documents: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    max_iterations: int = 8,
) -> AuditGraphState:
    return {
        "run_id": run_id,
        "user_id": user_id,
        "selected_document_version_ids": selected_document_version_ids,
        "documents": documents,
        "measurements": measurements,
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
        "quality_gate": {"ready": False, "reasons": []},
        "completed_agents": {},
        "route_history": [],
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "next_action": "audit_router",
        "needs_report_revision": False,
        "stop_reason": None,
        "errors": [],
    }
