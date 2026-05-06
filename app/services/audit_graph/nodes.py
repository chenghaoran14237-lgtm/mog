from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.audit_graph.state import AuditGraphState


def load_graph_state(state: AuditGraphState) -> dict:
    return _with_route(state, "load_graph_state", {"next_action": "audit_router"})


def audit_router(state: AuditGraphState) -> dict:
    completed = state.get("completed_agents", {})
    if not completed.get("document_quality_agent"):
        next_action = "document_quality_agent"
    elif not completed.get("timeline_builder"):
        next_action = "timeline_builder"
    elif not completed.get("measurement_consistency_agent"):
        next_action = "measurement_consistency_agent"
    elif not completed.get("risk_agent"):
        next_action = "risk_agent"
    elif _findings_need_evidence(state):
        next_action = "evidence_agent"
    elif not completed.get("conflict_agent"):
        next_action = "conflict_agent"
    elif _findings_need_evidence(state):
        next_action = "evidence_agent"
    elif not completed.get("compliance_agent"):
        next_action = "compliance_agent"
    elif not completed.get("quality_gate"):
        next_action = "quality_gate"
    elif state.get("needs_report_revision") or not state.get("report_draft"):
        next_action = "report_composer"
    else:
        next_action = "report_composer"

    return _with_route(state, "audit_router", {"next_action": next_action})


def document_quality_agent(state: AuditGraphState) -> dict:
    findings: list[dict[str, Any]] = []
    documents = state.get("documents", [])
    if not documents:
        findings.append(
            {
                "id": "quality:no_documents",
                "severity": "critical",
                "title": "未选择可审计文档",
                "description": "本次运行没有读取到文档版本，无法生成完整审计报告。",
                "evidence_ids": [],
            }
        )
    for document in documents:
        document_id = document.get("document_version_id")
        if not document.get("raw_text"):
            findings.append(
                {
                    "id": f"quality:empty_text:{document_id}",
                    "severity": "high",
                    "title": "文档缺少 OCR 原文",
                    "description": f"{document.get('display_name') or document_id} 缺少可追溯原文。",
                    "document_version_id": document_id,
                    "evidence_ids": [],
                }
            )
        if not document.get("report_date"):
            findings.append(
                {
                    "id": f"quality:missing_date:{document_id}",
                    "severity": "medium",
                    "title": "文档缺少报告日期",
                    "description": f"{document.get('display_name') or document_id} 未能识别报告日期。",
                    "document_version_id": document_id,
                    "evidence_ids": [],
                }
            )
    return _with_route(state, "document_quality_agent", {"quality_findings": findings})


def timeline_builder(state: AuditGraphState) -> dict:
    timeline: list[dict[str, Any]] = []
    for document in state.get("documents", []):
        timeline.append(
            {
                "type": "document",
                "at": document.get("report_date"),
                "title": document.get("display_name") or f"文档版本 {document.get('document_version_id')}",
                "document_version_id": document.get("document_version_id"),
            }
        )
    for measurement in state.get("measurements", []):
        timeline.append(
            {
                "type": "measurement",
                "at": measurement.get("observed_at"),
                "title": f"{measurement.get('name')} {measurement.get('value_text')}{measurement.get('unit') or ''}",
                "document_version_id": measurement.get("document_version_id"),
            }
        )
    timeline.sort(key=lambda item: item.get("at") or "")
    return _with_route(state, "timeline_builder", {"timeline": timeline})


def measurement_consistency_agent(state: AuditGraphState) -> dict:
    findings: list[dict[str, Any]] = []
    for measurement in state.get("measurements", []):
        value = measurement.get("value_numeric")
        if value is None:
            continue
        rule = _metric_rule(str(measurement.get("name") or ""))
        if rule is None:
            continue
        direction = None
        threshold = None
        if "high" in rule and value > rule["high"]:
            direction = "高于审计阈值"
            threshold = rule["high"]
        if "low" in rule and value < rule["low"]:
            direction = "低于审计阈值"
            threshold = rule["low"]
        if direction is None:
            continue
        metric_name = str(measurement.get("name") or "")
        findings.append(
            {
                "id": f"consistency:abnormal:{_safe_id(metric_name)}:{measurement.get('document_version_id')}",
                "type": "abnormal_metric",
                "severity": rule.get("severity", "medium"),
                "metric_name": metric_name,
                "title": f"{metric_name}{direction}",
                "description": f"{metric_name}={measurement.get('value_text')} {measurement.get('unit') or ''}，审计阈值为 {threshold}。",
                "document_version_id": measurement.get("document_version_id"),
                "evidence_ids": [],
            }
        )
    return _with_route(state, "measurement_consistency_agent", {"consistency_findings": findings})


def risk_agent(state: AuditGraphState) -> dict:
    findings: list[dict[str, Any]] = []
    for finding in state.get("consistency_findings", []):
        if finding.get("type") != "abnormal_metric":
            continue
        findings.append(
            {
                "id": f"risk:{finding['id']}",
                "severity": finding.get("severity", "medium"),
                "title": f"需关注：{finding.get('metric_name')}",
                "description": f"{finding.get('metric_name')} 出现异常，建议结合病历记录和后续复查结果复核。",
                "source_finding_id": finding.get("id"),
                "metric_name": finding.get("metric_name"),
                "document_version_id": finding.get("document_version_id"),
                "requires_evidence": True,
                "evidence_ids": [],
            }
        )
    if not findings:
        findings.append(
            {
                "id": "risk:no_obvious_structured_risk",
                "severity": "info",
                "title": "未发现明确结构化异常指标",
                "description": "基于当前结构化指标未发现需要优先复核的异常项。",
                "requires_evidence": False,
                "evidence_ids": [],
            }
        )
    return _with_route(state, "risk_agent", {"risk_findings": findings})


def evidence_agent(state: AuditGraphState) -> dict:
    evidence_items = list(state.get("evidence_items", []))
    evidence_by_id = {item.get("id"): item for item in evidence_items}
    for document in state.get("documents", []):
        document_version_id = document.get("document_version_id")
        evidence_id = f"document:{document_version_id}:raw"
        raw_text = str(document.get("raw_text") or "").strip()
        if raw_text and evidence_id not in evidence_by_id:
            evidence_by_id[evidence_id] = {
                "id": evidence_id,
                "kind": "document_text",
                "document_version_id": document_version_id,
                "field_name": "normalized_payload.raw_text",
                "source_label": document.get("display_name") or f"文档版本 {document_version_id}",
                "quote": raw_text[:180],
            }
    for measurement in state.get("measurements", []):
        metric_name = str(measurement.get("name") or "")
        evidence_id = f"measurement:{measurement.get('document_version_id')}:{_safe_id(metric_name)}"
        if evidence_id not in evidence_by_id:
            evidence_by_id[evidence_id] = {
                "id": evidence_id,
                "kind": "measurement",
                "document_version_id": measurement.get("document_version_id"),
                "field_name": "measurements.value_numeric",
                "metric_name": metric_name,
                "source_label": metric_name,
                "quote": f"{metric_name}={measurement.get('value_text')} {measurement.get('unit') or ''}".strip(),
            }

    evidence_items = list(evidence_by_id.values())
    risk_findings = [_attach_matching_evidence(finding, evidence_items) for finding in state.get("risk_findings", [])]
    consistency_findings = [
        _attach_matching_evidence(finding, evidence_items) for finding in state.get("consistency_findings", [])
    ]
    conflict_findings = [_attach_matching_evidence(finding, evidence_items) for finding in state.get("conflict_findings", [])]

    return _with_route(
        state,
        "evidence_agent",
        {
            "evidence_items": evidence_items,
            "risk_findings": risk_findings,
            "consistency_findings": consistency_findings,
            "conflict_findings": conflict_findings,
            "citation_issues": [],
            "needs_report_revision": bool(state.get("report_draft")),
        },
    )


def conflict_agent(state: AuditGraphState) -> dict:
    findings: list[dict[str, Any]] = []
    narrative_text = " ".join(
        str(document.get("raw_text") or "")
        for document in state.get("documents", [])
        if document.get("document_category") != "structured_metrics"
    )
    has_diabetes_denial = any(token in narrative_text for token in ["否认糖尿病", "无糖尿病", "无糖尿病史"])
    high_glucose = [
        measurement
        for measurement in state.get("measurements", [])
        if "糖" in str(measurement.get("name") or "") and (measurement.get("value_numeric") or 0) >= 7
    ]
    if has_diabetes_denial and high_glucose:
        findings.append(
            {
                "id": "conflict:diabetes_denial_high_glucose",
                "severity": "medium",
                "title": "病历叙述与血糖指标存在复核点",
                "description": "病历中出现否认糖尿病史表述，同时结构化指标存在血糖升高，需要人工结合诊疗背景复核。",
                "evidence_ids": _matching_evidence_ids("糖", state.get("evidence_items", []))
                + _matching_evidence_ids("否认糖尿病", state.get("evidence_items", [])),
            }
        )
    return _with_route(state, "conflict_agent", {"conflict_findings": findings})


def compliance_agent(state: AuditGraphState) -> dict:
    unresolved = [finding for finding in state.get("risk_findings", []) if finding.get("requires_evidence") and not finding.get("evidence_ids")]
    findings = [
        {
            "id": "compliance:traceability",
            "severity": "medium" if unresolved else "info",
            "title": "审计结论可追溯性检查",
            "description": "存在未绑定证据的风险结论。" if unresolved else "关键风险结论均已绑定结构化或原文证据。",
            "unresolved_count": len(unresolved),
            "evidence_ids": [],
        }
    ]
    return _with_route(state, "compliance_agent", {"compliance_findings": findings})


def quality_gate(state: AuditGraphState) -> dict:
    reasons: list[str] = []
    if not state.get("documents"):
        reasons.append("未读取到文档")
    if _findings_need_evidence(state):
        reasons.append("存在未补全证据的结论")
    gate = {"ready": not reasons, "reasons": reasons}
    return _with_route(state, "quality_gate", {"quality_gate": gate})


def report_composer(state: AuditGraphState) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    risk_findings = state.get("risk_findings", [])
    conflict_findings = state.get("conflict_findings", [])
    quality_findings = state.get("quality_findings", [])
    report = {
        "title": "多文档医疗审计综合报告",
        "generated_at": generated_at,
        "summary": _summary_text(state),
        "sections": [
            {
                "id": "sources",
                "title": "一、数据来源",
                "content": f"本次审计读取 {len(state.get('documents', []))} 份文档版本、{len(state.get('measurements', []))} 条结构化指标。",
            },
            {
                "id": "quality",
                "title": "二、文档质量审计",
                "content": _render_findings(quality_findings, "未发现影响审计的文档质量问题。"),
            },
            {
                "id": "risks",
                "title": "三、风险与异常指标",
                "content": _render_findings(risk_findings, "未发现明确结构化异常风险。"),
            },
            {
                "id": "conflicts",
                "title": "四、跨文档一致性",
                "content": _render_findings(conflict_findings, "未发现明确跨文档矛盾。"),
            },
            {
                "id": "conclusion",
                "title": "五、审计结论",
                "content": "本报告用于医疗文档质量与一致性审计，不替代医生诊断；所有异常项应结合临床背景复核。",
            },
        ],
        "findings": {
            "quality": quality_findings,
            "consistency": state.get("consistency_findings", []),
            "risk": risk_findings,
            "conflict": conflict_findings,
            "compliance": state.get("compliance_findings", []),
        },
        "evidence_items": state.get("evidence_items", []),
    }
    return _with_route(
        state,
        "report_composer",
        {
            "report_draft": report,
            "needs_report_revision": False,
        },
    )


def citation_checker(state: AuditGraphState) -> dict:
    issues: list[dict[str, Any]] = []
    for bucket_name in ["risk_findings", "conflict_findings", "consistency_findings"]:
        for finding in state.get(bucket_name, []):
            if finding.get("severity") == "info":
                continue
            if not finding.get("evidence_ids"):
                issues.append(
                    {
                        "id": f"citation:{finding.get('id')}",
                        "finding_id": finding.get("id"),
                        "bucket": bucket_name,
                        "message": f"{finding.get('title')} 缺少证据绑定。",
                    }
                )
    return _with_route(state, "citation_checker", {"citation_issues": issues})


def safety_reviewer(state: AuditGraphState) -> dict:
    report_text = str(state.get("report_draft") or "")
    issues = []
    for token in ["确诊", "治愈", "必须立即用药"]:
        if token in report_text:
            issues.append({"id": f"safety:{token}", "message": f"报告包含不适合审计场景的医学表达：{token}"})
    return _with_route(state, "safety_reviewer", {"safety_issues": issues})


def final_router(state: AuditGraphState) -> dict:
    iteration_count = int(state.get("iteration_count") or 0) + 1
    max_iterations = int(state.get("max_iterations") or 8)
    updates: dict[str, Any] = {"iteration_count": iteration_count}

    if iteration_count >= max_iterations and (state.get("citation_issues") or state.get("safety_issues")):
        updates.update({"next_action": "persist_report", "stop_reason": "max_iterations_reached"})
    elif state.get("citation_issues"):
        updates.update({"next_action": "audit_router", "needs_report_revision": True, "stop_reason": "citation_retry"})
    elif state.get("safety_issues"):
        updates.update({"next_action": "report_composer", "needs_report_revision": True, "stop_reason": "safety_retry"})
    else:
        updates.update({"next_action": "persist_report", "stop_reason": "completed"})
    return _with_route(state, "final_router", updates)


def persist_report(state: AuditGraphState) -> dict:
    final_report = state.get("final_report") or state.get("report_draft") or {}
    return _with_route(state, "persist_report", {"final_report": final_report})


def _with_route(state: AuditGraphState, node_name: str, updates: dict[str, Any]) -> dict[str, Any]:
    completed = dict(state.get("completed_agents") or {})
    completed[node_name] = int(completed.get(node_name) or 0) + 1
    return {
        **updates,
        "completed_agents": completed,
        "route_history": list(state.get("route_history") or []) + [node_name],
    }


def _findings_need_evidence(state: AuditGraphState) -> bool:
    for bucket_name in ["risk_findings", "conflict_findings", "consistency_findings"]:
        for finding in state.get(bucket_name, []):
            if finding.get("severity") != "info" and not finding.get("evidence_ids"):
                return True
    return bool(state.get("citation_issues"))


def _metric_rule(name: str) -> dict[str, Any] | None:
    normalized = name.lower()
    if "alt" in normalized or "谷丙" in normalized:
        return {"high": 40, "severity": "medium"}
    if "糖" in name or "glucose" in normalized or "hba1c" in normalized:
        return {"high": 7, "severity": "high"}
    if "crp" in normalized or "c反应" in normalized:
        return {"high": 10, "severity": "medium"}
    if "白细胞" in name or "wbc" in normalized:
        return {"high": 10, "severity": "medium"}
    return None


def _attach_matching_evidence(finding: dict[str, Any], evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    if finding.get("evidence_ids"):
        return finding
    metric_name = str(finding.get("metric_name") or finding.get("title") or "")
    evidence_ids = _matching_evidence_ids(metric_name, evidence_items)
    if not evidence_ids and "糖" in metric_name:
        evidence_ids = _matching_evidence_ids("糖", evidence_items)
    if not evidence_ids and "ALT" in metric_name.upper():
        evidence_ids = _matching_evidence_ids("ALT", evidence_items)
    return {**finding, "evidence_ids": evidence_ids, "requires_evidence": bool(finding.get("requires_evidence")) and not evidence_ids}


def _matching_evidence_ids(token: str, evidence_items: list[dict[str, Any]]) -> list[str]:
    if not token:
        return []
    token_lower = token.lower()
    ids = []
    for item in evidence_items:
        haystack = f"{item.get('metric_name') or ''} {item.get('quote') or ''} {item.get('source_label') or ''}".lower()
        if token_lower in haystack:
            ids.append(str(item.get("id")))
    return ids


def _render_findings(findings: list[dict[str, Any]], empty_text: str) -> str:
    visible = [finding for finding in findings if finding.get("severity") != "info" or len(findings) == 1]
    if not visible:
        return empty_text
    return "\n".join(f"- {finding.get('title')}：{finding.get('description')}" for finding in visible)


def _summary_text(state: AuditGraphState) -> str:
    risk_count = len([finding for finding in state.get("risk_findings", []) if finding.get("severity") != "info"])
    conflict_count = len(state.get("conflict_findings", []))
    return f"完成 {len(state.get('documents', []))} 份文档的状态机审计，发现 {risk_count} 个风险关注项、{conflict_count} 个跨文档复核点。"


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.strip()) or "unknown"
