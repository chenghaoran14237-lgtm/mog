from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from langgraph.graph import END, START, StateGraph

from app.services.audit_graph.nodes import (
    audit_router,
    citation_checker,
    compliance_agent,
    conflict_agent,
    document_quality_agent,
    evidence_agent,
    final_router,
    load_graph_state,
    measurement_consistency_agent,
    persist_report,
    quality_gate,
    report_composer,
    risk_agent,
    safety_reviewer,
    timeline_builder,
)
from app.services.audit_graph.state import AuditGraphState


AUDIT_GRAPH_EDGES = [
    ("__start__", "load_graph_state"),
    ("load_graph_state", "audit_router"),
    ("audit_router", "document_quality_agent"),
    ("document_quality_agent", "audit_router"),
    ("audit_router", "timeline_builder"),
    ("timeline_builder", "audit_router"),
    ("audit_router", "measurement_consistency_agent"),
    ("measurement_consistency_agent", "audit_router"),
    ("audit_router", "risk_agent"),
    ("risk_agent", "audit_router"),
    ("audit_router", "evidence_agent"),
    ("evidence_agent", "audit_router"),
    ("audit_router", "conflict_agent"),
    ("conflict_agent", "audit_router"),
    ("audit_router", "compliance_agent"),
    ("compliance_agent", "audit_router"),
    ("audit_router", "quality_gate"),
    ("quality_gate", "audit_router"),
    ("audit_router", "report_composer"),
    ("report_composer", "citation_checker"),
    ("citation_checker", "safety_reviewer"),
    ("safety_reviewer", "final_router"),
    ("final_router", "audit_router"),
    ("final_router", "report_composer"),
    ("final_router", "persist_report"),
    ("persist_report", "__end__"),
]


@dataclass(slots=True)
class AuditGraphStep:
    node_name: str
    edge_source: str
    edge_target: str
    output: dict
    state: AuditGraphState


class AuditGraphEngine:
    def __init__(self, recursion_limit: int = 100) -> None:
        self.recursion_limit = recursion_limit
        self._compiled_graph = build_audit_graph()

    def run(self, initial_state: AuditGraphState) -> AuditGraphState:
        final_state = dict(initial_state)
        for step in self.stream(initial_state):
            final_state = dict(step.state)
        return final_state

    def stream(self, initial_state: AuditGraphState) -> Iterator[AuditGraphStep]:
        state: AuditGraphState = dict(initial_state)
        previous_node = "__start__"
        for chunk in self._compiled_graph.stream(state, config={"recursion_limit": self.recursion_limit}):
            if not chunk:
                continue
            node_name, output = next(iter(chunk.items()))
            state = {**state, **output}
            yield AuditGraphStep(
                node_name=node_name,
                edge_source=previous_node,
                edge_target=node_name,
                output=output,
                state=state,
            )
            previous_node = node_name


def build_audit_graph():
    graph = StateGraph(AuditGraphState)
    graph.add_node("load_graph_state", load_graph_state)
    graph.add_node("audit_router", audit_router)
    graph.add_node("document_quality_agent", document_quality_agent)
    graph.add_node("timeline_builder", timeline_builder)
    graph.add_node("measurement_consistency_agent", measurement_consistency_agent)
    graph.add_node("risk_agent", risk_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.add_node("conflict_agent", conflict_agent)
    graph.add_node("compliance_agent", compliance_agent)
    graph.add_node("quality_gate", quality_gate)
    graph.add_node("report_composer", report_composer)
    graph.add_node("citation_checker", citation_checker)
    graph.add_node("safety_reviewer", safety_reviewer)
    graph.add_node("final_router", final_router)
    graph.add_node("persist_report", persist_report)

    graph.add_edge(START, "load_graph_state")
    graph.add_edge("load_graph_state", "audit_router")
    graph.add_conditional_edges(
        "audit_router",
        _route_from_audit_router,
        {
            "document_quality_agent": "document_quality_agent",
            "timeline_builder": "timeline_builder",
            "measurement_consistency_agent": "measurement_consistency_agent",
            "risk_agent": "risk_agent",
            "evidence_agent": "evidence_agent",
            "conflict_agent": "conflict_agent",
            "compliance_agent": "compliance_agent",
            "quality_gate": "quality_gate",
            "report_composer": "report_composer",
        },
    )
    for node_name in [
        "document_quality_agent",
        "timeline_builder",
        "measurement_consistency_agent",
        "risk_agent",
        "evidence_agent",
        "conflict_agent",
        "compliance_agent",
        "quality_gate",
    ]:
        graph.add_edge(node_name, "audit_router")
    graph.add_edge("report_composer", "citation_checker")
    graph.add_edge("citation_checker", "safety_reviewer")
    graph.add_edge("safety_reviewer", "final_router")
    graph.add_conditional_edges(
        "final_router",
        _route_from_final_router,
        {
            "audit_router": "audit_router",
            "report_composer": "report_composer",
            "persist_report": "persist_report",
        },
    )
    graph.add_edge("persist_report", END)
    return graph.compile()


def _route_from_audit_router(state: AuditGraphState) -> str:
    return str(state.get("next_action") or "report_composer")


def _route_from_final_router(state: AuditGraphState) -> str:
    return str(state.get("next_action") or "persist_report")
