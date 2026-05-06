from __future__ import annotations


def build_health_analysis_fallback(
    *,
    prompt: str,
    context_text: str,
    document_count: int,
    reason: str | None = None,
) -> str:
    evidence = _extract_evidence(context_text)
    reason_text = f"；原因：{_compact(reason)}" if reason else ""
    evidence_block = "\n".join(f"- {item}" for item in evidence) if evidence else "- 当前上下文未提供足够的结构化指标，只能给出保守建议。"

    return (
        f"当前 AI 模型网关暂时不可用{reason_text}。以下内容由系统基于已入库 OCR 文本、结构化指标和文档上下文生成，"
        "用于保证流程连续，不替代医生诊断。\n\n"
        "一、核心判断\n"
        f"- 本次已选择 {document_count} 份文档。问题是：{prompt.strip() or '综合分析当前健康文档'}。\n"
        "- 系统已完成基础数据读取，但暂时无法调用大模型做深度推理，因此结论保持保守。\n\n"
        "二、我最关注的风险点\n"
        "- 若报告中存在超出参考范围、持续升高或症状加重的信息，应优先复查并线下就诊确认。\n"
        "- 单次报告只能反映当次状态，趋势判断需要结合多次检查和临床症状。\n\n"
        "三、接下来怎么做\n"
        "- 先核对原始报告、OCR 结果和结构化指标是否准确。\n"
        "- 对异常指标按医生建议复查；如涉及血糖、血脂、肝肾功能等项目，建议保留同一检测机构的连续数据。\n"
        "- AI 网关恢复后，可重新生成完整智能分析报告。\n\n"
        "四、哪些情况要尽快就医\n"
        "- 出现胸痛、呼吸困难、意识异常、持续高热、明显乏力加重、严重腹痛或指标显著异常时，应尽快线下就医。\n\n"
        "五、我的依据\n"
        f"{evidence_block}"
    )


def _extract_evidence(context_text: str) -> list[str]:
    lines = []
    for raw_line in context_text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        if len(line) > 140:
            line = f"{line[:137]}..."
        lines.append(line)
        if len(lines) >= 6:
            break
    return lines


def _compact(value: str | None) -> str:
    text = " ".join((value or "").split()).strip()
    return text[:120]
